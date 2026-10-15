# 考古与历史研究周刊

公开静态网站。仓库：[HalaMarkPang/archaeology-review](https://github.com/HalaMarkPang/archaeology-review)。地址：[https://halamarkpang.github.io/archaeology-review/](https://halamarkpang.github.io/archaeology-review/)。

托管使用 GitHub Pages 与 GitHub Actions 的免费额度，不另设服务器，不使用付费模型接口。

## 模型

Skill 的构建与周刊的产出使用 **Grok 4.7 High**。

Skill 指编选规范、检索配置与页面结构的编写。周刊产出指各期中文说明的撰写。这两部分依赖该模型的表述与取舍。更换模型后，同一批材料可能得到不同的分段、用词与去留，不能假定结果与现行刊期一致。

中文期刊、发掘报告与会议纪要本身不是模型生成的。模型只用于阅读已核对材料并写成周刊正文。`scripts/discover.py` 与 `scripts/review.py` 不调用模型，也不改写摘要原句。

## 可配置项

检索周期与关注内容都在 [`config/discovery.json`](config/discovery.json)。页面上的时代、体裁与独立分组由构建程序读取该文件，不写死在模板中。刊期起讫由各期 JSON 的 `period` 生成，不写死某一期的日期。

| 键 | 作用 |
|---|---|
| `schedule.timezone`、`schedule.cron` | 定时检索的时区与时刻。须与 [`.github/workflows/research.yml`](.github/workflows/research.yml) 中的 `timezone`、`cron` 一致。测试会核对此二者。 |
| `lookback_days` | 自运行日向前追溯的天数。 |
| `max_issue_items` | 一期收录上限。 |
| `max_per_period` | 同一时代或独立分组的上限。 |
| `periods` | 时代、识别词与检索式。 |
| `fields` | 专业领域、识别词与检索式。 |
| `standalone_group` | 不标时代、单独成组的领域。当前为考古学理论。 |
| `genres` | 体裁名称与页面顺序。 |
| `journal_watches`、`priority_journals`、`core_journals` | 关注期刊。 |
| `wechat_accounts` | 关注的公众号。未核完不等于该号没有文章。 |
| `official_watch_pages`、`chinese_toc_indexes`、`chinese_issue_lists` | 机构页面、目录页与出刊信息。 |
| `umbrella_queries`、`china_anchors`、`pinned_dois` | 总检索、中国相关锚点、指定 DOI。 |

修改运行时刻时，同时修改 `schedule` 与 `research.yml`。只改其中一处，定时任务与配置会分叉。

编选规则见 [`config/research-policy.md`](config/research-policy.md)。

## 发布

Pages 的 Source 须为 GitHub Actions。推送到 `main` 后，[`.github/workflows/pages.yml`](.github/workflows/pages.yml) 执行 `scripts/build.py`，生成静态页面与 Pagefind 中文检索索引，并发布。站点不使用数据库。

`content/issues/` 中的正式刊期进入首页与归档。`is_sample` 为真的文件只作版式样刊，不计入正式归档。候选、审计与状态文件不是已发表结论。

## 定时检索

[`research.yml`](.github/workflows/research.yml) 按 `schedule` 运行，也可在 Actions 中手动执行。

1. `discover.py` 按配置采集 Crossref 元数据、已配置的期刊与机构页面，以及公众号线索。配置 `OPENALEX_API_KEY` 时同时采集 OpenAlex；该密钥为免费密钥，不配置则跳过。
2. 候选题录写入 `content/candidates/`。第三方完整摘要不进入公开仓库。
3. `review.py` 只接受能够逐字对应摘要原文的摘录。证据不足时不新增正式刊期，并写入 `content/status.json` 与 `content/audits/`。
4. 已提交的变更推送到 `main` 后，触发 Pages 重新构建。

自动摘录不是全文校读，也不是模型改写。墓志释文、甲骨字形与正式发掘结论，须核对原文后再写入刊期。

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

无外网时，只能核验数据校验与静态构建，不能据此认为外部检索已经完成。GitHub 的定时工作流可能延迟；公开仓库长期无活动时，定时任务也可能被暂停。

## 依据

- Crossref API: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- OpenAlex API: https://help.openalex.org/api/
- GitHub Actions 调度: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- GitHub Pages 自定义工作流: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- Pagefind 中文检索: https://github.com/Pagefind/pagefind/blob/main/docs/content/docs/multilingual.md
