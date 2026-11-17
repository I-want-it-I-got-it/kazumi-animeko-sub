#!/usr/bin/env python3
"""Mimic Animeko web-selector auto-match for one keyword: search -> ALL subjects (sorted by name length) -> each detail page.
Reports per-source timing, subject count, channels, episode counts/ranges.
Usage: KW=名侦探柯南 python3 crawl_like_animeko.py sub.json [source names...]"""
import json, os, re, sys, time
import requests
from bs4 import BeautifulSoup
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
KW = os.environ.get("KW", "名侦探柯南")
S = requests.Session(); S.headers["User-Agent"] = UA
requests.packages.urllib3.disable_warnings()
TOK = re.compile(r"\[\*\]|\['([^']+)'\]|\.([A-Za-z_]\w*)")

def jp(obj, expr):
    cur = [obj]
    for m in TOK.finditer(expr[1:]):
        nxt = []
        for c in cur:
            if m.group(0) == "[*]":
                nxt += c if isinstance(c, list) else []
            else:
                k = m.group(1) or m.group(2)
                if isinstance(c, dict) and k in c: nxt.append(c[k])
        cur = nxt
    return cur

def absu(h, base):
    if h.startswith("http"): return h
    if h.startswith("//"): return "https:" + h
    return base.rstrip("/") + "/" + h.lstrip("/")

DEFAULT_MATCH_CH = r"^(?<ch>.+?)(\d+)?$"   # Animeko SelectorChannelFormatIndexGrouped 默认值

def jsoup_text(e):
    return " ".join(e.get_text(" ").split())

def chip_label(text, cc):
    """按 Animeko 规则算出选源面板里显示的线路名 (= Media.properties.alliance)。None 表示该线路被丢弃。"""
    expr = cc.get("matchChannelName", DEFAULT_MATCH_CH)
    if not text:
        return None
    if expr == "":
        return text
    m = re.search(expr.replace("(?<", "(?P<"), text)
    if not m:
        return None
    return m.groupdict().get("ch") or text

def sel(doc, css):
    try: return doc.select(css)
    except Exception as e: return "ERR:" + str(e)[:60]

def run(src):
    a = src["arguments"]; c = a["searchConfig"]
    url = c["searchUrl"].replace("{keyword}", requests.utils.quote(KW))
    base = c.get("rawBaseUrl") or re.match(r"https?://[^/]+", url).group(0)
    rep = dict(name=a["name"], search_url=url)
    t0 = time.time()
    try:
        r = S.get(url, timeout=20, verify=False)
    except Exception as e:
        rep["search"] = "ERR " + type(e).__name__ + " " + str(e)[:80]; return rep
    rep["search_http"] = r.status_code; rep["search_s"] = round(time.time()-t0, 2)
    if r.url != url: rep["final_url"] = r.url
    if "cf-chl" in r.text or "Just a moment" in r.text: rep["cloudflare"] = True
    subs = []
    f = c["subjectFormatId"]
    if f == "json-path-indexed":
        try: js = r.json()
        except Exception: rep["search"] = "non-JSON: " + r.text[:80].replace("\n"," "); return rep
        sc = c["selectorSubjectFormatJsonPathIndexed"]
        ns, ls = jp(js, sc["selectNames"]), jp(js, sc["selectLinks"])
        subs = [(str(n), absu(sc.get("linkTemplate","{value}").replace("{value}", str(l)), base)) for n, l in zip(ns, ls)]
    else:
        doc = BeautifulSoup(r.text, "lxml")
        if f == "indexed":
            sc = c["selectorSubjectFormatIndexed"]
            ns, ls = sel(doc, sc["selectNames"]), sel(doc, sc["selectLinks"])
            subs = [(n.get_text(" ", strip=True), absu(l.get("href",""), base)) for n, l in zip(ns, ls)]
        else:
            ls = sel(doc, c["selectorSubjectFormatA"]["selectLists"])
            subs = [(l.get("title") or l.get_text(" ", strip=True), absu(l.get("href",""), base)) for l in ls]
    subs.sort(key=lambda x: len(x[0]))
    rep["subjects"] = len(subs)
    details = []
    for n, u in subs:
        t1 = time.time()
        try:
            d = S.get(u, timeout=20, verify=False, headers={"Referer": url})
        except Exception as e:
            details.append(dict(n=n[:20], u=u, err=type(e).__name__)); continue
        doc = BeautifulSoup(d.text, "lxml")
        info = dict(n=n[:20], u=u, http=d.status_code, kb=len(d.content)//1024, s=round(time.time()-t1, 2))
        if c["channelFormatId"] == "index-grouped":
            cc = c["selectorChannelFormatFlattened"]
            chs, lists = sel(doc, cc["selectChannelNames"]), sel(doc, cc["selectEpisodeLists"])
            if isinstance(chs, str) or isinstance(lists, str):
                info["err"] = chs if isinstance(chs, str) else lists
            else:
                info["ch_raw"] = [jsoup_text(x)[:24] for x in chs]
                info["chips"] = [chip_label(jsoup_text(x), cc) for x in chs][:len(lists)]
                eps = [[e.get_text(" ", strip=True) for e in L.select(cc["selectEpisodesFromList"])] for L in lists]
                info["eps"] = [len(e) for e in eps]
                info["range"] = [(e[0][:8], e[-1][:8]) if e else None for e in eps]
        else:
            eps = sel(doc, c["selectorChannelFormatNoChannel"]["selectEpisodes"])
            if isinstance(eps, str): info["err"] = eps
            else:
                t = [e.get_text(" ", strip=True) for e in eps]
                info["eps"] = len(t); info["range"] = (t[0][:8], t[-1][:8]) if t else None
                info["chips"] = [""]  # no-channel: 线路名恒为空
        details.append(info)
    rep["total_s"] = round(time.time()-t0, 1)
    rep["details"] = details
    return rep

if __name__ == "__main__":
    sub = json.load(open(sys.argv[1]))
    want = set(sys.argv[2:])
    for s in sub["mediaSources"]:
        if want and s["arguments"]["name"] not in want: continue
        print(json.dumps(run(s), ensure_ascii=False), flush=True)
