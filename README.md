# 考古与历史研究周刊

公开静态网站。仓库：[HalaMarkPang/archaeology-review](https://github.com/HalaMarkPang/archaeology-review)。地址：[https://halamarkpang.github.io/archaeology-review/](https://halamarkpang.github.io/archaeology-review/)。

站点由 GitHub Pages 与 GitHub Actions 的免费额度托管。

## 检索与产出

每周五 18:37（上海时间）运行 [`.github/workflows/research.yml`](.github/workflows/research.yml)，也可在 Actions 中手动执行。检索窗口为运行日向前 `lookback_days` 天。时刻、窗口、时代、领域、期刊与公众号都以 [`config/discovery.json`](config/discovery.json) 为准。

检索这些材料：

- 时代：旧石器、新石器、商周、战国秦汉、魏晋南北朝、隋唐、宋元明。辽代、辽金、宋金归入宋元明。时代止于宋元明。
- 专业领域：科技考古、建筑考古、美术考古。考古学理论按学科单独成组。
- 体裁：发掘简报、调查简报、发掘报告、出土文献、馆藏研究、研究论文。
- 来源：配置中的期刊、机构页面、目录与公众号；Crossref；配置了免费密钥 `OPENALEX_API_KEY` 时的 OpenAlex；总检索式与指定 DOI。

一次运行写出这些结果：

| 产物 | 内容 |
|---|---|
| `content/candidates/日期.json` | 候选题录：题名、作者、期刊、日期、链接，以及时代与领域的初步归类。摘要原文留在本地缓存。 |
| `content/audits/日期.json`、`content/status.json` | 每条的核验结果，以及本期候选数、达标数、新刊数。 |
| `content/issues/日期.json` | 正式刊期。摘录与摘要原文逐字对应、并且达到收录标准时写入。同日文件已存在时，保留原刊期。 |
| GitHub Pages | 上述变更推送到 `main` 后，[`.github/workflows/pages.yml`](.github/workflows/pages.yml) 用正式刊期生成静态页面与 Pagefind 中文检索，发布到站点地址。 |

一期条数见 `max_issue_items`，同一时代或考古学理论一组的条数见 `max_per_period`。编选细则见 [`config/research-policy.md`](config/research-policy.md)。

## 模型

Skill 的构建与周刊的产出使用 **Grok 4.7 High**。

Skill 指编选规范、检索配置与页面结构的编写。周刊产出指各期中文说明的撰写。这两部分依赖该模型的表述与取舍。更换模型后，同一批材料的分段、用词与去留随之改变，现行刊期保留的是当前模型的成稿。

中文期刊、发掘报告与会议纪要来自已发表原文。模型阅读已核对材料，写成周刊正文。`scripts/discover.py` 与 `scripts/review.py` 负责采集与校验，摘录保持摘要原句。

## 可配置项

检索周期与关注内容都在 [`config/discovery.json`](config/discovery.json)。页面上的时代、体裁与独立分组由构建程序读取该文件。刊期起讫由各期 JSON 的 `period` 生成。

| 键 | 作用 |
|---|---|
| `schedule.timezone`、`schedule.cron` | 定时检索的时区与时刻。与 [`.github/workflows/research.yml`](.github/workflows/research.yml) 中的 `timezone`、`cron` 保持一致。测试会核对此二者。 |
| `lookback_days` | 自运行日向前追溯的天数。 |
| `max_issue_items` | 一期收录上限。 |
| `max_per_period` | 同一时代或独立分组的上限。 |
| `periods` | 时代、识别词与检索式。 |
| `fields` | 专业领域、识别词与检索式。 |
| `standalone_group` | 单独成组的领域。当前为考古学理论。 |
| `genres` | 体裁名称与页面顺序。 |
| `journal_watches`、`priority_journals`、`core_journals` | 关注期刊。 |
| `wechat_accounts` | 关注的公众号。翻页中断的账号记为尚未核完。 |
| `official_watch_pages`、`chinese_toc_indexes`、`chinese_issue_lists` | 机构页面、目录页与出刊信息。 |
| `umbrella_queries`、`china_anchors`、`pinned_dois` | 总检索、中国相关锚点、指定 DOI。 |

运行时刻在 `schedule` 与 `research.yml` 两处使用同一组时区与 cron。

## 发布

Pages 的 Source 设为 GitHub Actions。推送到 `main` 后，`pages.yml` 执行 `scripts/build.py`，生成静态页面与中文检索索引，并发布。

`content/issues/` 中的正式刊期进入首页与归档。`is_sample` 为真的文件作版式样刊。候选、审计与状态文件记录检索与核验过程。

## 本地运行

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/build.py
python -m http.server 8000 --directory site
```

浏览器打开 `http://localhost:8000`。

联网采集：

```bash
python scripts/discover.py
python scripts/review.py
python scripts/build.py
```

离线时可核验数据校验与静态构建。外部检索以联网采集的结果为准。GitHub 定时工作流按平台队列执行，可能晚于设定时刻。公开仓库长期无活动时，平台会暂停定时任务。

## 依据

- Crossref API: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- OpenAlex API: https://help.openalex.org/api/
- GitHub Actions 调度: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- GitHub Pages 自定义工作流: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- Pagefind 中文检索: https://github.com/Pagefind/pagefind/blob/main/docs/content/docs/multilingual.md
