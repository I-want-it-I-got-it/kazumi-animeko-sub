# kazumi-animeko-sub

把 [Predidit/KazumiRules](https://github.com/Predidit/KazumiRules) 的 Kazumi 规则转写成 Animeko 的 `web-selector` 订阅。

## 订阅地址

```
https://raw.githubusercontent.com/I-want-it-I-got-it/kazumi-animeko-sub/main/kazumi-animeko-sub.json
```

Animeko：设置 → 数据源管理 → 数据源订阅右侧 `+` → 粘贴上面的地址。

## 内容

仓库现有 86 条 Kazumi 规则，其中 68 条标为 `deprecated`（Kazumi 客户端不展示，未转）。在役的 18 条中：

| 状态 | 数量 | 说明 |
|---|---|---|
| 已转写并验证 | 14 | 搜索与选集两层在真实页面命中 |
| 不可转 / 不转 | 4 | 章节走 JSON 接口、源站已改版，或与其他源同站 |

已验证的源：7sefun、AGE、DM84、LMM、MXdm、TvTFun、akianime、baimao、dalvdm、ezdmw、giriGiriLove、mgnacg、moonci（mutefun 因 Cloudflare 403 未完成验证）。

未转写：aafun（与 moonci 同为 www.moonci.com，只保留 moonci）、sorani（章节走 JSON 接口）、xfdmnext（POST 接口）、xfdmneo（源站已改版为 xifan.moe）。

## 字段落位

| Kazumi | Animeko |
|---|---|
| searchURL（@keyword） | searchUrl（{keyword}） |
| searchList + searchName + searchResult | subjectFormatId: indexed |
| searchMode: api + sourceTemplate | json-path-indexed + linkTemplate |
| chapterRoads / chapterResult | index-grouped 的 selectEpisodeLists / selectEpisodesFromList |
| 无（Kazumi 内部合成「播放线路N」） | selectChannelNames，从详情页 tab 节点补 |
| baseURL | rawBaseUrl |
| referer / userAgent | matchVideo.addHeadersToVideo |

Kazumi 的 searchName / searchResult 是对每条结果节点求值，chapterResult 是对每条线路节点求值；Animeko 的搜索段是文档级选择器按顺序 zip，选集段才作用在线路容器内，所以搜索段要拼成「行选择器 + 名称选择器」的写法。

## 已知限制

- AGE 的详情链接由源站写成 http，个别网络会 504。
- ezdmw 的剧集是线路标签的兄弟节点，CSS 无法按线路分组，只取主线。
- 7sefun 用到 `:has()`，Android 端 jsoup 1.18 支持；iOS 端异常时改为 no-channel 取主线。baimao 已改为不依赖 `:has()`。
- Animeko 会按顺序抓取**每一条**搜索结果的详情页，全部抓完才结束该源的加载（列表里一直转圈）。热门长篇（如名侦探柯南）一搜就是十几到三十多个结果，所以 DM84、baimao、7sefun 的搜索结果选择器用 `:nth-child(-n+N)` 只取前 N 条（7sefun 详情页单页 2–6 秒，取 6 条；DM84、baimao 取 8 条）。
- mutefun 搜索返回 403（Cloudflare），实际能否通过取决于设备网络。

## 维护

站点改版时（`.github/workflows/verify.yml` 每天自动跑一次校验，结果见 Actions 摘要），改生成脚本 `PROFILES` 里对应源的 CSS，重新生成并跑一遍 `verify_sub.py`（抓真实页面校验搜索结果数、线路数、首集数），再替换仓库里的 JSON。

`tools/crawl_like_animeko.py` 按 Animeko 的方式（搜索 → 逐个抓所有结果的详情页）测每个源的总耗时：`KW=名侦探柯南 python3 tools/crawl_like_animeko.py kazumi-animeko-sub.json DM84 7sefun`。
