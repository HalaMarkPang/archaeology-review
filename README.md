# 考古与历史研究周刊｜GitHub Pages 自动化项目

**公开网站；商周优先；每周五检索；先证据后发布。**

本项目实现 GitHub Pages 静态网站、每期独立 HTML、归档与 Pagefind 中文检索；另有定时学术元数据采集、机器审校、候选与审核轨迹记录以及通过严格门槛的自动刊期生成。首次部署时暂无正式刊期；未通过来源核验的候选不会出现在首页或正式归档。

## 一、先部署网站

1. 项目仓库：**[HalaMarkPang/archaeology-review](https://github.com/HalaMarkPang/archaeology-review)**，公开 `main` 分支；代码和工作流已经提交。
3. `Settings → Pages → Build and deployment → Source` 选择 `GitHub Actions`。
4. `Actions → Build and deploy archaeology review → Run workflow`，确认部署成功。
5. 网址一般为 `https://<用户名>.github.io/archaeology-review/`。第一次部署时会显示“尚无正式刊期”，这是正确行为。

**重要：** 在本仓库 `Settings → Pages → Build and deployment → Source` 选择 `GitHub Actions`；此设置不能通过当前 GitHub 连接直接修改。完成后访问 `https://halamarkpang.github.io/archaeology-review/`。配置 API Key 前不会自动生成正式研究推荐。

网站构建工作流：`.github/workflows/pages.yml`，每次 `main` 更新或手动执行都会重新生成静态网站及 Pagefind 中文检索索引。静态站点不需要数据库、服务器或 Web 管理后台。

## 二、启用自动研究

仓库 `Settings → Secrets and variables → Actions` 配置：

| 名称 | 类型 | 必需 | 用途 |
|---|---|---|---|
| `OPENALEX_API_KEY` | Secret | 建议 | OpenAlex 2026 年免费 API Key，生产使用建议配置；不填则只请求 Crossref 和官方公开页面 |
| `MODEL_API_KEY` | Secret | 自动写作必需 | 模型服务的 API Key，绝不要提交进源码 |
| `MODEL_NAME` | Variable | 自动写作必需 | API 服务实际支持的模型 ID，由所选服务商提供 |
| `MODEL_API_BASE_URL` | Variable | 可选 | OpenAI-compatible Chat Completions 端点的 API 前缀，默认 `https://api.openai.com/v1` |
| `PUBLISH_MODE` | Variable | 可选 | 默认为 `candidates_only`（仅采集和审核）；设置 `auto_verified` 才允许合格摘要自动形成刊期 |

> 注意：ChatGPT 网页版订阅不等于 API 调用额度。只有仓库设置了有效的 `MODEL_API_KEY`、`MODEL_NAME`，机器摘要审校才会运行。模型必须兼容 `/chat/completions`。如所选模型输出不支持所需 JSON/格式，当前脚本会拒绝条目，不能确保零配置即能工作。

`.github/workflows/research.yml`：每周五**北京时间 18:37**运行一次（IANA 时区 `Asia/Shanghai`），也可在 Actions 手动运行。流程为：

1. **采集**：Crossref DOI 元数据、OpenAlex 元数据与摘要、文物出版社网站的公开新信息线索；可用的站点/关键词在 `config/discovery.json` 中配置。
2. **初选**：商周、甲骨、金文、墓志、发掘简报及人物家族研究优先；检查发表日期、论文类型、DOI 和跨期重复。
3. **候选归档**：只把题录、链接、是否含摘要及得分写入 `content/candidates/YYYY-MM-DD.json`；**不将获得的第三方完整摘要提交到公开仓库**。
4. **摘要审校**：只有有效 DOI、近 30 天完整发表日期、足够完整的摘要，以及模型至少两条**逐字匹配摘要原文的证据片段**，才能进入自动发表条件；模型返回不合格将拒绝。
5. **自动发表**：通过的最多 5 项形成 `content/issues/YYYY-MM-DD.json`。缺少证据就**不新增期号**，并写入 `content/status.json` 与 `content/audits/`。
6. **自动部署**：研究脚本将已核验的期刊 JSON、候选元数据和审计轨迹提交到 `main`，触发 Pages 重新生成首页、独立刊期与归档。

默认只自动发表**已核对公开摘要**的 B 级成果，绝不将其伪称为全文校读。正式发掘报告、完整墓志释文、甲骨字形与释读等 A 级内容，需要编辑逐项核对后手工添加。**摘要引用片段匹配只是一项最低校验，不构成完全的事实或学术正确性证明。** 已发表 B 级内容需保留“机器摘要提取，未经人工全文复核”提示。

## 三、国内期刊覆盖边界

《考古》《文物》《考古与文物》《考古学报》等中文期刊在国际元数据库中可能不完整。当前自动线索检测仅包含**已配置的两处公开出版资讯页面**；这些页面上的标题和期刊目录只进入候选池，**不能自动生成证据与历史结论**。

要达到中文成果每周较完整的覆盖，还须分期加入：

- 各刊官方目录公开渠道（特别是《考古》《考古与文物》）的稳定可读取源；
- 合规检索服务/可访问的出版方摘要源；
- 出土文献与墓志整理的原文资料核对工作；
- 必要时进行人工确认或加入人工批准的完整 JSON 条目。

**因此，当前代码是可运行的自动研究与发布基础，不声称已实现对全部中文重要期刊的自动全文覆盖。** 没有达到发表门槛的资料进入候选，不应凑数。

## 四、内容结构与来源等级

- `content/issues/*.json`：经过审核的正式周报，可人工新增明确标记 `is_sample` 的版式样刊；网页只把正式刊期计入归档。
- `content/candidates/*.json`：题录候选，不能当作已核查结论。
- `content/audits/*.json`：简化核查记录，避免公开转载全文摘要。
- `content/status.json`：最后执行日期、采集数量和发布结果。
- `config/discovery.json`：主题偏好、检索词、来源页和回溯区间。
- `scripts/discover.py`：元数据发现、官方页面线索扫描。
- `scripts/review.py`：模型辅助审查与证据片段校验。
- `scripts/build.py`：静态页面和归档生成。

核查等级：

- **A 已核对全文**：需人工阅读论文/报告，核实引文、铭文、墓志及相关证据，方能刊出细节。
- **B 已核对公开摘要**：只转述提供方摘要支持的事实与作者解释；自动条目须标记未经全文审校。
- **C 仅核对目录**：只保存书目信息及出处链接，不准编写核心证据、墓主身份或学术结论。

每项建议包含原始出处、核心发现、关键证据、学术价值、局限、新旧研究性质与阅读链接；发表日期和实际发掘日期应分开记录。允许只发表 1—2 项或某周不发表。不同期 DOI、题名去重。

## 五、本地运行

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/build.py
python -m http.server 8000 --directory site
```

浏览器打开 `http://localhost:8000`。

联网采集：

```bash
export OPENALEX_API_KEY='在本地环境变量提供，不要写进源码'
python scripts/discover.py
# 将候选放在 .cache/discovery.json；完整摘要仅保留在 .cache（Git 忽略）
export MODEL_API_KEY='...'
export MODEL_NAME='服务商支持的模型ID'
python scripts/review.py
python scripts/build.py
```

本地无外网时只能测试数据校验与静态构建，不能据此声称真实检索 API 已经成功工作。GitHub Actions 定时运行可能延迟或被丢弃；公开仓库若长期无活动，GitHub 也可能暂停定时工作流。

## 六、原始资料与实现依据

- Crossref API: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- Crossref 出版日期过滤: https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/
- OpenAlex API: https://help.openalex.org/api/
- OpenAlex 认证: https://help.openalex.org/api/authentication/
- GitHub Actions 时区与调度: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- GitHub Pages 自定义工作流: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- Pagefind 中文检索: https://github.com/Pagefind/pagefind/blob/main/docs/content/docs/multilingual.md