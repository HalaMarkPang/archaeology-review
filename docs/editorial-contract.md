# 模型稿与证据合同

`python scripts/editorial.py`将`.cache/discovery.json`导出为`.cache/editorial-packet.json`。每个item包含原始candidate和sources；sources包含公开摘要的原文、url、材料类型及指纹。需要全文或纪要时，可在采集记录的`source_materials`补充真实取得的材料，字段为`url`、`text`和`material_type`；再次导出会计算指纹。允许类型为公开摘要、全文、会议纪要、新闻披露、报刊文章。目录不能作为摘要补入。

完整证据包仅用于本地撰写和复核，不提交到公开仓库。

## 撰写文件

`.cache/drafts.json`包含`intro`和`records`。每条必须保留candidate的id、title、doi、url和published_date；书目需要更正时先更正采集依据，不能在稿件中无说明替换。

正文记录必须包含：

| 字段 | 内容 |
|---|---|
| id、title、doi、authors | 条目标识、原题名、DOI、完整作者。非DOI材料的doi可为空 |
| publication、published_date、url | 刊载信息、实际发表日期及精度、出处 |
| headline、core | 中文题名与正文，段落以两个换行分隔，不留空段 |
| significance | 必填评述。材料研究显示为“研究意义”；理论组显示为“对研究实践的启示”，说明观点对实际工作及解释方法的影响。篇幅按问题确定，不统一字数或句数 |
| period、kind、material_type | 配置内的时代/理论分组与体裁，以及真实材料性质 |
| source_status、limits | 所取得的材料程度与核对范围。目录不得发布 |
| evidence | 可公开的简短核对要点；不冒称逐字引文 |
| generation | model、prompt_version、generated_at，均按实际执行填写 |
| claims | 顺序对应headline（存在时）、core的每段、significance的每段 |

claims的每项包含`text`和`supports`。text必须与对应的完整标题/段落一致。supports的每项包含`quote`、`url`、`source_hash`：quote为12—240个字符的原文片段；url和source_hash分别对应证据包中的来源地址和指纹。每段可引用多个片段。形式匹配不代表该片段一定支持整段，语义关系由复核步骤检查。

研究意义不必复述原文结论。原文支持的事实可作为编者分析的起点，但须在正文中明确哪些是进一步的比较方向或问题；supports对应其事实前提。涉及“修正此前认识”时，还须有此前认识的出处，不能仅凭新材料反推学界过去的观点。补读材料按同样方式加入证据包。程序拒绝缺失或空白的significance；是否具体、有解释力，由最终稿复核负责。

理论条目的正文须让读者理解争论的前因后果，再在significance中说明实际工作会怎样受到影响。可以用具体例子解释概念，例子须明确为说明性举例，不能冒称原作者的案例。页面名称由理论分组决定，不另设一套证据或复核途径。

## 最终稿复核

复核执行者阅读原文与最终稿，在`.cache/review.json`的records对象中，以条目id为键写入：

| 字段 | 要求 |
|---|---|
| status | reviewed |
| reviewer_type | model或human，如实填写 |
| reviewer、reviewed_at | 实际复核执行者与日期 |
| record_digest | 最终记录指纹，由`editorial.record_digest(record)`计算 |
| claims_supported | 标题、发现正文和研究意义的事实有来源支持；编者推论与其依据相符，true才可发布 |
| uncertainty_preserved | 推测程度未被升级，true才可发布 |
| scope_confirmed | 分类及适用范围已核对，true才可发布 |
| sources_checked | 所列来源已经实际阅读，true才可发布 |

不得用脚本把四项一律写true以代替阅读复核。没有完成检查时保持待复核。任何标题、正文、证据或书目信息变更后，必须重新核对并更新指纹。

先用`review.py --dry-run`检查，再使用同一稿件和复核文件加`--publish`导入。所有候选均记录去向，篇数和分组上限只影响最后选刊；新刊期写入前通过与build相同的验证器。

首期的历史迁移记录只用于保留既有31条及其有限复核说明，不作为后续稿件的发布途径。
