#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kazumi rules -> Animeko (web-selector) subscription converter.

输入: KazumiRules 仓库 (index.json + 每条 *.json)
输出: Animeko schemaVersion=2 订阅 JSON

用法:
  python3 kazumi2animeko.py --rules ./kazumi_rules --out kazumi-animeko-sub.json
  可选 --all 转换全部规则（含 deprecated），否则只转换 index.json 中的在役规则
"""
import argparse, json, os, re, sys

# ---------------------------------------------------------------------------
# 每个站点的人工核对结果（基于 2026-11 实际页面抓取）
# 字段说明:
#   search: {kind: html|json, url, names, links, template}
#   chapter: {kind: index-grouped|no-channel, names, lists, eps, match}
# ---------------------------------------------------------------------------
PROFILES = {
    "7sefun": dict(
        search=dict(kind="html",
                    url="https://www.7sefun.top/vodsearch/-------------.html?wd={keyword}",
                    names="div.videos > div.video.anim:nth-child(-n+6) > div.video-by",
                    links="div.videos > div.video.anim:nth-child(-n+6) a.video-wrapper"),
        chapter=dict(kind="index-grouped",
                     names="div.chat:has(.vod-play-list-container) > div.chat-header.anim",
                     lists="div.message-container.vod-play-list-container",
                     eps="a", match="(?<ch>[^\\s]+线)$"),
    ),
    "AGE": dict(
        search=dict(kind="html",
                    url="https://www.agedm.io/search?query={keyword}",
                    names="div.card.cata_video_item h5.card-title",
                    links="div.card.cata_video_item a.d-block"),
        # 该站 6 条线路没有可用的线路名节点，只取第一条主线，避免 6 份同号剧集并列
        chapter=dict(kind="no-channel",
                     eps="div.tab-content > div.tab-pane:nth-of-type(1) ul.video_detail_episode a"),
    ),
    "DM84": dict(
        search=dict(kind="html",
                    url="https://dmbus.cc/s----------.html?wd={keyword}",
                    names="ul.v_list > li:nth-child(-n+8) > div.item > a.title",
                    links="ul.v_list > li:nth-child(-n+8) > div.item > a.title"),
        chapter=dict(kind="index-grouped",
                     names="ul.tab_control.play_from > *",
                     lists="div.tab_content > ul.play_list",
                     eps="li > a", match=""),
    ),
    "MXdm": dict(
        search=dict(kind="html",
                    url="https://www.dcc3.com/search/?wd={keyword}",
                    names="div.search.container > ul > li > h3 > a",
                    links="div.search.container > ul > li > h3 > a"),
        chapter=dict(kind="index-grouped",
                     names="div.playlist div.tabs > *",
                     lists="div.playlist > div.row > ul",
                     eps="li > a", match=""),
    ),
    "akianime": dict(
        search=dict(kind="html",
                    url="https://www.akianime.cc/bgmsearch/-------------.html?wd={keyword}",
                    names="div.vod-detail.search-list div.detail-info > a",
                    links="div.vod-detail.search-list a[href*='/bgmplay/']"),
        chapter=dict(kind="index-grouped",
                     names="div.anthology-tab a",
                     lists="ul.anthology-list-play.size",
                     eps="li > a", match=""),
    ),
    "baimao": dict(
        search=dict(kind="html",
                    url="https://www.bmddm.com/s_all?ex=1&kw={keyword}",
                    names="div.lpic > ul > li:nth-child(-n+8) h2 > a",
                    links="div.lpic > ul > li:nth-child(-n+8) h2 > a"),
        chapter=dict(kind="index-grouped",
                     names="div.tabs > ul.menu0 > li",
                     lists="div.movurl > ul",
                     eps="li > a", match=""),
    ),
    "ezdmw": dict(
        search=dict(kind="html",
                    url="https://m.ezdmw.org/Index/search.html?searchText={keyword}",
                    names="section#some_drama > div p",
                    links="section#some_drama > div a"),
        # 剧集链接是线路标签的兄弟节点，无法按“线路容器”分组；取主线
        chapter=dict(kind="no-channel",
                     eps="section.anthology a.circuit_switch1"),
    ),
    "mutefun": dict(
        search=dict(kind="html",
                    url="https://www.mutedm.com/search?q={keyword}",
                    names="section[class*='search-results-section'] a[class*='video-card'] span[class*='video-card-title']",
                    links="section[class*='search-results-section'] a[class*='video-card']"),
        chapter=dict(kind="index-grouped",
                     names="div[class*='episode-panel'] div[class*='episode-list']",
                     lists="div[class*='episode-panel'] div[class*='episode-list']",
                     eps="a", match=""),
    ),
    # ---- JSON 搜索 ----
    "LMM": dict(
        search=dict(kind="json",
                    url="https://www.lmm22.com/index.php/ajax/suggest?mid=1&wd={keyword}",
                    names="$.list[*]['name']",
                    links="$.list[*]['id']",
                    template="https://www.lmm22.com/index.php/vod/detail/id/{value}.html"),
        chapter=dict(kind="index-grouped",
                     names="div.module-tab-content > div.module-tab-item",
                     lists="div.module-player-list",
                     eps="div.module-blocklist a", match=""),
    ),
    "dalvdm": dict(
        search=dict(kind="json",
                    url="https://www.sbdl.cc/index.php/ajax/suggest?mid=1&wd={keyword}",
                    names="$.list[*]['name']",
                    links="$.list[*]['id']",
                    template="https://www.sbdl.cc/index.php/vod/detail/id/{value}.html"),
        chapter=dict(kind="index-grouped",
                     names="ul.swiper-wrapper > li.swiper-slide a.swiper-slide-text",
                     lists="div.tab-pane.lists-box",
                     eps="div.listitem a", match=""),
    ),
    "mgnacg": dict(
        search=dict(kind="json",
                    url="https://www.mgnacg.com/index.php/ajax/suggest?mid=1&wd={keyword}",
                    names="$.list[*]['name']",
                    links="$.list[*]['id']",
                    template="https://www.mgnacg.com/media/{value}"),
        chapter=dict(kind="index-grouped",
                     names="div.anthology-tab a",
                     lists="ul.anthology-list-play.size",
                     eps="li > a", match=""),
    ),
    "moonci": dict(
        search=dict(kind="json",
                    url="https://www.moonci.com/index.php/ajax/suggest?mid=1&wd={keyword}",
                    names="$.list[*]['name']",
                    links="$.list[*]['id']",
                    template="https://www.moonci.com/anime/{value}.html"),
        chapter=dict(kind="index-grouped",
                     names="a.hl-tabs-btn",
                     lists="ul.hl-plays-list",
                     eps="li > a", match=""),
    ),
    "TvTFun": dict(
        search=dict(kind="json",
                    url="https://www.tvtfun.net/api/client/anime?keyword={keyword}&page=1&pageSize=24",
                    names="$.data.items[*]['name']",
                    links="$.data.items[*]['slug']",
                    template="https://www.tvtfun.net/watch/{value}/1"),
        chapter=dict(kind="no-channel", eps="ol.tvt-watch-episodes a"),
    ),
    "giriGiriLove": dict(
        search=dict(kind="json",
                    url="https://m3u8.girigirilove.com/api.php/Vod/get_list?offset=0&limit=24&vod_name={keyword}",
                    names="$.info.rows[*]['vod_name']",
                    links="$.info.rows[*]['vod_id']",
                    template="/GV{value}/"),
        chapter=dict(kind="index-grouped",
                     names=".anthology-tab > .swiper-wrapper > a",
                     lists=".anthology-list > .anthology-list-box",
                     eps=".anthology-list-play a[href]",
                     match="^(?<ch>.+?)(?:\\s*\\d+)?$"),
        raw_base="https://bg.girigirilove.com",
        match_video=dict(enableNestedUrl=False, matchNestedUrl="",
                         matchVideoUrl=r"(?i)(?:^|[?&]url=)(?<v>https?://[^\s#]+?\.(?:m3u8|mpd|mp4|m4v|mkv|webm)(?:\?[^\s#]*)?)(?=&|$)",
                         cookies="", addHeadersToVideo=dict(referer="https://ani.girigirilove.com/")),
    ),
}

# Animeko web-selector 表达不了的规则（章节接口型 / 页面无静态剧集），以及有意不转的重复源
UNSUPPORTED = {
    "aafun": "与 moonci 是同一站点（www.moonci.com），重复转写会对同站加倍请求并触发 403 限流，只保留 moonci",
    "sorani": "章节走 JSON 接口，站点详情页为 Svelte 动态渲染，无静态剧集节点",
    "xfdmnext": "章节走 POST JSON 接口，web-selector 仅支持网页 DOM 解析",
    "xfdmneo": "源站已改版为 xifan.moe（Astro 前端渲染），旧规则里的 .thumb-txt/.thumb-menu 节点已不存在",
}

MATCH_EP = "第\\s*(?<ep>.+)\\s*[话集]"
MATCH_EP_LOOSE = "^(?:第\\s*)?(?<ep>\\d+(?:\\.\\d+)?)(?:\\s*[话話集])?$"


def build_source(rule_name: str, rule: dict, profile: dict) -> dict:
    s = profile["search"]
    c = profile["chapter"]
    name = rule.get("name", rule_name)
    disp = profile.get("display_name") or name

    if s["kind"] == "json":
        subject_fmt = "json-path-indexed"
        subj_cfg = {"selectNames": s["names"], "selectLinks": s["links"]}
        if s.get("template"):
            subj_cfg["linkTemplate"] = s["template"]
    elif s.get("subject_format") == "a":
        subject_fmt = "a"
        subj_cfg = {"selectLists": s["links"]}
    else:
        subject_fmt = "indexed"
        subj_cfg = {"selectNames": s["names"], "selectLinks": s["links"]}

    # 只写非默认字段；Animeko 的默认值已核对（1080P / CHS / filterByEpisodeSort=true /
    # selectMedia 两项为 true / matchVideo 为内置默认）
    cfg = {
        "searchUrl": s["url"],
        "subjectFormatId": subject_fmt,
        "channelFormatId": c["kind"],
    }
    if profile.get("raw_base"):
        cfg["rawBaseUrl"] = profile["raw_base"]

    if subject_fmt == "indexed":
        cfg["selectorSubjectFormatIndexed"] = subj_cfg
    elif subject_fmt == "json-path-indexed":
        cfg["selectorSubjectFormatJsonPathIndexed"] = subj_cfg
    else:
        cfg["selectorSubjectFormatA"] = subj_cfg

    if c["kind"] == "index-grouped":
        cfg["selectorChannelFormatFlattened"] = {
            "selectChannelNames": c["names"],
            **({"matchChannelName": c["match"]} if c.get("match") else {}),
            "selectEpisodeLists": c["lists"],
            "selectEpisodesFromList": c["eps"],
        }
    else:
        cfg["selectorChannelFormatNoChannel"] = {
            "selectEpisodes": c["eps"],
        }

    mv = profile.get("match_video")
    if mv:
        cfg["matchVideo"] = mv

    desc = f"由 KazumiRules 的 {name} v{rule.get('version','?')} 规则转写"
    src = {
        "id": "kazumi-" + re.sub(r"[^a-z0-9]+", "-", rule_name.lower()).strip("-"),
        "factoryId": "web-selector",
        "version": 2,
        "arguments": {
            "name": disp,
            "description": desc,
            "iconUrl": favicon(rule.get("baseURL") or s["url"]),
            "searchConfig": cfg,
            "tier": 2,
        },
    }
    return src


def favicon(base: str) -> str:
    m = re.match(r"https?://[^/]+", base or "")
    return (m.group(0) + "/favicon.ico") if m else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default="./kazumi_rules")
    ap.add_argument("--out", default="kazumi-animeko-sub.json")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--name", default="KazumiRules 转写订阅")
    args = ap.parse_args()

    index_path = os.path.join(args.rules, "index.json")
    active = {}
    if os.path.exists(index_path):
        for x in json.load(open(index_path, encoding="utf-8")):
            active[x["name"]] = x

    names = sorted(active) if not args.all else sorted(
        f[:-5] for f in os.listdir(args.rules) if f.endswith(".json") and f != "index.json"
    )

    out, skipped, reports = [], [], []
    for n in names:
        path = os.path.join(args.rules, n + ".json")
        if not os.path.exists(path):
            continue
        rule = json.load(open(path, encoding="utf-8"))
        if n in UNSUPPORTED:
            skipped.append({"name": n, "reason": UNSUPPORTED[n]})
            continue
        prof = PROFILES.get(n)
        if not prof:
            skipped.append({"name": n, "reason": "未提供核对过的选择器映射"})
            continue
        out.append(build_source(n, rule, prof))

    sub = {
        "schemaVersion": 2,
        "name": args.name,
        "description": "由 Predidit/KazumiRules 的 Kazumi 规则逐条转写为 Animeko web-selector 数据源",
        "websiteUrl": "https://github.com/Predidit/KazumiRules",
        "mediaSources": out,
    }
    json.dump(sub, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"已写入 {args.out}: {len(out)} 个数据源")
    if skipped:
        print("跳过:", json.dumps(skipped, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
