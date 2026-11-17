import json, re, sys, os
import requests
from bs4 import BeautifulSoup
requests.packages.urllib3.disable_warnings()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
KW = os.environ.get("KW", "葬送的芙莉莲")

def get(u, referer=None):
    try:
        return requests.get(u, headers={"User-Agent": UA, "Referer": referer or u}, timeout=30, verify=False)
    except Exception:
        return None

def T(n):
    try:
        return re.sub(r"\s+", " ", n.get_text(" ")).strip()
    except Exception:
        return ""

def jsonpath(obj, expr):
    if not expr.startswith("$"):
        return []
    body = expr[1:]
    if body.startswith("."):
        body = body[1:]
    tokens = []
    i = 0
    while i < len(body):
        if body[i] == ".":
            i += 1
        elif body.startswith("[*]", i):
            tokens.append("*"); i += 3
        elif body[i] == "[":
            j = body.index("]", i)
            inner = body[i + 1:j].replace("'", '"')
            keys = [k.strip().strip('"') for k in inner.split(",")]
            tokens.append(("keys", keys)); i = j + 1
        else:
            j = i
            while j < len(body) and body[j] not in ".[":
                j += 1
            tokens.append(("key", body[i:j])); i = j
    cur = [obj]
    for t in tokens:
        nxt = []
        for c in cur:
            if t == "*":
                if isinstance(c, list):
                    nxt += c
            elif isinstance(t, tuple) and t[0] == "keys":
                if isinstance(c, dict):
                    nxt += [c[k] for k in t[1] if k in c]
            elif isinstance(t, tuple) and t[0] == "key":
                if isinstance(c, dict) and t[1] in c:
                    nxt.append(c[t[1]])
        cur = nxt
    return cur

def absolutize(h, cfg, search_url):
    if not h:
        return None
    if h.startswith("http"):
        return h
    base = cfg.get("rawBaseUrl") or ("https://" + search_url.split("//")[1].split("/")[0])
    return base[:-1] + h if base.endswith("/") and h.startswith("/") else base + h

def parse_chapters(doc, cfg):
    if cfg["channelFormatId"] == "index-grouped":
        cc = cfg["selectorChannelFormatFlattened"]
        ch = doc.select(cc["selectChannelNames"])
        lists = doc.select(cc["selectEpisodeLists"])
        e0 = lists[0].select(cc["selectEpisodesFromList"]) if lists else []
        ok = bool(ch) and len(ch) == len(lists) > 0 and bool(e0)
        return dict(format="channels", channels=len(ch), lists=len(lists),
                    ch_names=[T(c)[:14] for c in ch[:6]],
                    eps=len(e0), ep_names=[T(e)[:10] for e in e0[:4]], ok=ok)
    cc = cfg["selectorChannelFormatNoChannel"]
    eps = doc.select(cc["selectEpisodes"])
    return dict(format="no-channel", eps=len(eps),
                ep_names=[T(e)[:10] for e in eps[:4]], ok=bool(eps))

def check(src):
    args, cfg = src["arguments"], src["arguments"]["searchConfig"]
    rep = {"id": src["id"], "name": args.get("name")}
    url = cfg["searchUrl"].replace("{keyword}", requests.utils.quote(KW))
    r = get(url)
    if r is None:
        rep["search"] = "请求失败"
        return rep
    rep["http"] = r.status_code
    links = []

    if cfg["subjectFormatId"] == "json-path-indexed":
        try:
            js = json.loads(r.text)
        except Exception:
            rep["search"] = "非 JSON 响应: " + r.text[:60].replace("\n", " ")
            return rep
        sc = cfg["selectorSubjectFormatJsonPathIndexed"]
        names = jsonpath(js, sc["selectNames"])
        links = jsonpath(js, sc["selectLinks"])
        tpl = sc.get("linkTemplate") or ""
        rep["names"], rep["links"] = len(names), len(links)
        rep["sample"] = [(str(names[i])[:26], str(links[i])[:30]) for i in range(min(2, len(names), len(links)))]
        links = [tpl.replace("{value}", str(x)) for x in links]
    else:
        doc = BeautifulSoup(r.text, "lxml")
        sc = cfg.get("selectorSubjectFormatIndexed") or cfg.get("selectorSubjectFormatA")
        nsel = sc.get("selectNames") or sc.get("selectLists")
        lsel = sc.get("selectLinks") or sc.get("selectLists")
        names_el = doc.select(nsel) if nsel else []
        links_el = doc.select(lsel) if lsel else []
        rep["names"], rep["links"] = len(names_el), len(links_el)
        rep["sample"] = [(T(e)[:26], (e.get("href") or "")[:30]) for e in names_el[:2]]
        links = [e.get("href") for e in links_el]

    rep["ok_search"] = rep["names"] > 0 and rep["links"] > 0
    cands = [absolutize(h, cfg, url) for h in links[:3]]
    cands = [c for c in cands if c]
    rep["detail_url"] = cands[0] if cands else None

    best = None
    for c in cands:
        tries = [c]
        if c.startswith("http://"):
            tries.insert(0, "https://" + c[len("http://"):])
        for t in tries:
            d = get(t, referer=url)
            if d is None or d.status_code >= 400:
                continue
            res = parse_chapters(BeautifulSoup(d.text, "lxml"), cfg)
            res["detail_url"] = t
            if best is None or (res["ok"] and not best["ok"]):
                best = res
            if res["ok"]:
                break
        if best and best["ok"]:
            break
    if best:
        rep.update(best)
    else:
        rep["detail"] = "详情页不可用"
    return rep

def main():
    sub = json.load(open(sys.argv[1], encoding="utf-8"))
    rows = []
    for s in sub["mediaSources"]:
        try:
            rep = check(s)
        except Exception as e:
            rep = {"id": s["id"], "error": str(e)[:150]}
        rows.append(rep)
        print(json.dumps(rep, ensure_ascii=False))
    json.dump(rows, open("validate_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for r in rows if r.get("ok_search") and r.get("ok"))
    print(f"\n通过 {ok}/{len(rows)}")

if __name__ == "__main__":
    main()
