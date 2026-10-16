# 考古-周刊

编选旧石器至宋元明的新公布考古材料、研究与理论讨论。网站：[考古-周刊](https://halamarkpang.github.io/archaeology-review/)。

## 内容与范围

中国考古为主要对象，兼收与其研究问题有关的国际理论和比较研究。辽、金材料归入宋元明；专论清代及以后者不进入正式刊期。时代、专业领域和体裁分别标注，会议纪要与学术演讲说明其真实材料类型。

本期31条由其他模型撰写。历史说明曾标注Grok 4.7 High，但没有逐条模型运行记录；不能据此还原每条的生成和核验过程。2026年10月16日对正文、出处说明及分类作了有限复核与修订，保留尚未重新取得材料的明确说明。首期覆盖2026年9月1日至10月14日，作为回溯编选，不套用后续普通刊期的篇数上限。

## 工作流程

采集题录与公开材料 → 导出本地证据包 → 模型撰写 → 复核最终正文 → 导入并发布。

每周五12:00（Asia/Shanghai），`research.yml`采集前30个日期范围内的材料，保留全部候选、来源覆盖与逐条处理状态。该工作流不调用模型，不把摘要摘句冒充中文编选稿。证据包作为有保留期限的运行附件保存，撰写时下载使用；没有稿件或复核文件时不会新增正式刊期。

模型可使用本地或交互式工具，项目不绑定付费API。撰写与复核按[编选规范](config/research-policy.md)执行，导入格式见[稿件与证据合同](docs/editorial-contract.md)。复核记录必须绑定最终正文；正文、标题或证据变化后，旧记录不再有效。程序检查结构、版本和引文匹配；断言是否得到支持仍须阅读原文判断。

## 检索与覆盖

唯一生效配置为`config/discovery.json`。API使用cursor翻页；达到预算、访问失败或页面解析受限时，记录部分完成，不宣称已经查全。中文目录中未识别时代的条目仍进入候选。搜狗微信只作搜索补充，不代表公众号完整历史列表。

`journal_identifiers`指定可确认的ISSN。未配置标识的期刊按刊名检索并严格核对刊名，仍可能受数据库收录情况限制。机构目录跟随可确认的下一页链接，不能识别分页边界时保留未核完状态。新来源应同时配置访问路径与核对方式，不能只增加名称。

题录去重使用DOI与规范题名，已经发表的作品也保留于本次处理记录；跨期再次发表须有实质更新说明。普通刊期默认最多12篇、每组最多4篇，最终数量取决于材料和复核结果。

## 本地运行

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/build.py
python -m http.server 8000 --directory site
```

打开`http://localhost:8000`。全站检索使用构建时生成的条目索引，无需另装索引工具；结果直接定位到固定刊期内的条目。

采集与准备撰写：

```bash
python scripts/discover.py
python scripts/editorial.py
python scripts/review.py
```

完成模型稿和独立复核后，按采集日期导入。`--date`必须与证据包日期相同：

```bash
python scripts/review.py --date 2026-10-16 --drafts .cache/drafts.json --review-file .cache/review.json --dry-run
python scripts/review.py --date 2026-10-16 --drafts .cache/drafts.json --review-file .cache/review.json --publish
python scripts/build.py
```

上述日期是命令示例，不会创建该日期刊期。正式文件写入`content/issues/`，同日刊期不会被覆盖。更正已有刊期须保留更正说明；首期历史迁移另有内容指纹，不能绕过更新校验。

## 产物与部署

| 位置 | 内容 |
|---|---|
| `content/candidates/` | 题录、来源覆盖及警告，不包含完整摘要 |
| `.cache/` | 原始摘要、补充原文、模型稿和本地证据包，不提交到公开仓库 |
| `content/audits/` | 每条候选的去向与处理原因 |
| `content/status.json` | 本次处理状态；历史刊期与运行状态分别理解 |
| `content/issues/` | 完成复核的正式刊期 |
| `content/corrections/` | 更正记录 |
| `content/migrations/` | 首期历史迁移指纹与有限复核范围 |

推送main后，Pages工作流先运行测试与统一内容校验，再构建并发布。采集工作流的bot提交通过显式dispatch触发Pages，保留原有部署方式。GitHub队列可能延迟定时任务，来源覆盖以运行记录为准。

参考：[Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)、[GitHub Actions调度](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。
