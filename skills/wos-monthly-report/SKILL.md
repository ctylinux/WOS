---
name: wos-monthly-report
description: "Use when 制作某高校某月WOS论文月报(检索/第一单位/分区/Excel交付)。"
version: 1.0.0
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [research, web-of-science, wos, 月报, 第一单位, 中科院分区, excel, china, playwright, bibliometrics, 高校学科发展智能支持平台]
    related_skills: [institutional-database-access, cas-journal-partition]
---

# 高校学科发展智能支持平台（高校 WOS 论文收录智能分析月报系统）

> **对外名称：高校学科发展智能支持平台**（技术标识仍为 `wos-monthly-report`，脚本路径不变）。
> 从"某高校 + 某月"出发，产出可直接用于科研考核与学科建设的 Excel 月报/季报：每篇论文一行，含
**第一单位归属、篇名、作者、期刊来源、入库时间(DA)、正式出版时间(PD)、EA时间**，
以及期刊的**中科院分区**列。

本技能是**编排层（runbook）**：把已验证的步骤、口径、坑位串成一条可重复执行的流水线。
底层细节不在这里重复——
- 访问/检索/导出/EA/第一单位判定的完整细节与选择器 → 技能 `institutional-database-access`
  （含 `references/web-of-science-search-export.md`，务必先读）。
- 期刊中科院分区的抓取与解析 → 技能 `cas-journal-partition`（含 `scripts/letpub_cas_parse.py`）。

## When to Use

- 用户要"某高校某月（如 2026年7月）WOS 收录情况/月报"，并要求其中或追加字段（第一单位、
  分区、EA 等）。
- 需要把"某机构 + 某月"的 WOS 结果整理成 Excel 交付，且要求区分"第一单位是否本校"。
- **不适用**：单篇论文检索、文献综述、纯 OpenAlex/知网统计（那些走 `academic-literature-search`）。

## 参数确认（先定口径，再动手）

动手前明确或直接声明以下口径（用户未说就按括号内默认，并在交付时说明）：

| 参数 | 说明 |
|------|------|
| 机构英文名 | WOS 机构字段全部罗马化，中文检索 0 结果。如 闽南师范大学 = `Minnan Normal University`；海南师范大学 = `Hainan Normal University` |
| 月份窗口 | 检索字段用 **Publication Date**，范围 YYYY-MM-01 ~ 当月最后一天（季报即 YYYY-01-01 ~ YYYY-03-31，脚本不用改） |
| 数据库范围 | 默认 **All Databases**（含 6 合集）；权威"被WOS收录"口径可用 Core Collection |
| 正式发表 | 剔除预印本/非期刊记录：UT 前缀 `PPRN:`（arXiv 预印本，DT=preprint）与 `RC:`（Research Commons，常无题名） |
| 第一单位 | 默认"第一作者单位"；评估口径也可能要"通讯作者单位"，交付时说明并可选再出一版 |
| 分区版本 | 中科院分区表"2025升级版"= LetPub 当前非"旧"的 `（2025年3月升级版）` 表 |

机构改名（如 漳州师范学院 → 闽南师范大学）要确认 WOS 是否用现名匹配，旧名论文可能漏检。

## 流水线总览

```
确认参数 → ①All Databases 检索+导出 → ②剔除预印本/RC → ③核心合集 Full Record 导出取 C1
        → ④第一单位判定 → ⑤去重期刊查中科院分区 → ⑥构建 Excel+CSV → ⑦验证 → ⑧交付
        → ⑨学院贡献率饼图 → ⑩手绘思维导图信息图（⑨⑩为月报固定附加交付）
```

### 阶段 0 — 环境与访问

- **先试 IP 直连**：`webofscience.clarivate.cn/wos/alldb/basic-search`，用**无 storage_state 的全新
  context**。校园网内通常已由 IP 授权（页脚 `Sign in to access <机构>`），完全免登录、且不受
  CARSI 会话 ~10 分钟过期限制。若跳 `webofknowledge.com/error?...Error=shibboleth,ip` 再走 CARSI。
- 本地 Chromium + 库前缀（无 sudo）：
  `LD_LIBRARY_PATH=/tmp/chrome-libs/usr/lib/x86_64-linux-gnu` +
  `~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome`；venv = `~/.hermes/hermes-agent/venv`。
  安装/补齐与 CARSI 细节见 `institutional-database-access` Step 0。
- 用 Python playwright 直接驱动，**不要**用 `browser_exec`（其后端从 Google CDN 拉 Chrome，国内失败）。

### 阶段 1 — All Databases 检索 + 导出

用 `scripts/wos_alldb_search_export.py <机构英文名> <起> <止> <输出TSV>`：

- 字段选 **Address**（All Databases 无 Affiliation）；查询值=机构英文名；Publication Date=Custom。
- 结果数从页面标题 `"<机构> (Address) – N – All Databases"` 读取。
- 导出：结果页头部 `Export`（不是 `Export Refine`）→ `Tab delimited file` →
  **范围切到 `Records from 1 to N`**（默认 "All records on page" 只导首页 50 条，静默丢数据）
  → 模态框 `Export`。
- **All Databases 导出永远没有 C1/AB**（内容选项只有 Author,Title,Source /+Abstract /
  Custom selection，没有 Full Record）。所以 C1 必须另取（阶段 3）。
- 记录数校验：导出后先数一遍 `非空行数 == N`。

### 阶段 2 — 只保留"正式发表"

读导出 TSV（**按列索引解析**：表头有重复列名 `AU`，`csv.DictReader` 会丢作者）：
- 保留 UT 前缀 `WOS:` / `MEDLINE:`；丢弃 `PPRN:` / `RC:`。
- 交付说明里写清：原始 N 条、剔除 M 条（预印本/RC）、正式发表 K 条。

### 阶段 3 — 第一单位判定（需 C1）

用 `scripts/woscc_full_export.py <机构英文名> <起> <止> <输出TSV>`：

- 在 **Core Collection**（`/wos/woscc/basic-search`）用字段 **Affiliation** 重搜同月；
- 导出时把 Record Content 切到 **Full Record**（按文本点 `button` 文本 = 当前内容级别
  如 "Author, Title, Source" → 再点文本为 "Full Record" 的元素；选项不在 `.cdk-overlay-container mat-option` 下）；
  同样记得范围 `1..N`。→ 得到带 C1 的 TSV。
- 按 UT 与阶段 2 的主表 join；判定：C1 第一组 `[作者] 机构`（正则
  `^\[([^\]]*)\]\s*(.*?)(?:;\s*\[|$)`）是否含该校（`MINNAN NORMAL UNIV` 等缩写）。
- 主表里 C1 缺失的记录（woscc `Affiliation` 比 `Address` 更严，会漏几条）：逐条开
  `wos/woscc/full-record/<UT>` 读 `Addresses` 段——**地址 1 = 第一单位**；
  `MEDLINE:<pmid>` 记录无编号列表，取首条地址。
- 预期相当比例是"合作/挂名"（第一单位是别校），要如实分开统计并列出例外。

### 阶段 4 — 中科院分区

去重期刊 `SO`（ISSN 取 `SN`，空则 `EI`），逐刊查 LetPub——完整做法与坑位见
`cas-journal-partition`，其 `scripts/letpub_cas_parse.py` 负责解析。

本技能的 `scripts/letpub_cas_fetch.py` 是带**缓存复用 + 限流退避 + 断点续跑**的抓取器：
先加载上一次任何一家机构的 raw JSON 作缓存（期刊列表跨机构/月份高度重复），只抓缺失的；
限流（搜索框消失 → `no input`）时等待 60–120s 再跑，每轮 10 条左右、间隔 5–15s。

**已验证的驱动方式（31 刊、0 失败、约 21 分钟）**：写一个 shell 驱动脚本，按**每批 5 刊**循环调用
（`letpub_cas_fetch.py JOURNALS.json RAW.json START END --cache 旧raw1 --cache 旧raw2`），
**批间 `sleep 75`**，起止从 0 递增到期刊总数；脚本每抓一刊即落盘，中途被杀可从断点续跑。
用 `terminal(background=True, notify=True)` 跑，别在前台等（必然超过超时）。

### 阶段 5 — 构建 Excel

用 `scripts/build_report_excel.py`，列（本用户既定格式）：

```
序号 | <机构>是否第一单位 | 篇名 | 作者 | 期刊来源 |
中科院大类学科 | 大类分区 | 小类分区 | Top期刊 | 入库时间 | 正式出版时间 | EA时间
```

- 表头深蓝底白字加粗、冻结首行、自动筛选、细边框；"是否第一单位"列绿(是)/红(否)着色。
- 日期**归一化**：`AUG 27 2026` / `AUG 2026` / `2026-Aug-27` → `YYYY-MM-DD`（无日则 `YYYY-MM`）。
  混用原始格式在下游会被当成数据错误。
- 第二个 sheet `说明`：检索对象/数据库/字段/值、时间范围、检索日期、原始条数、剔除数、
  正式发表数、分区来源与版本、第一单位判定口径、第一单位与分区分布统计、字段说明。
- 同时导出同名 `.csv`（UTF-8 BOM，便于 Excel 直接打开）。

### 阶段 6 — 验证（不许跳过）

- 行数 == 正式发表条数；每篇都匹配到分区（无分区数=0，或明确列出未收录的刊）。
- 第一单位 是/否、分区 1/2/3/4 区计数与脚本自身计数一致，且合计=总条数。
- 抽查 3–4 条"否"的原始 C1 分段，确认第一作者确在别校（避免解析误判）。
- 重新打开生成的 xlsx 断言表头名与行数（防静默丢行/错列）。

### 阶段 8 — 月报附加交付：① 学院贡献率饼图　② 手绘思维导图信息图

本用户的月报流程**固定包含**这两步（不只做 Excel）。

**① 学院贡献率饼图** — `scripts/college_pies.py`（底层用 `scripts/pie3d.py` 手绘风3D饼图）：

```bash
python3 college_pies.py <报告.csv> <c1.json> <parsed.json> <输出目录> <标签> [--period 2026-06]
```

- 默认统计"第一单位=本校"的全部记录；加 `--period` 只算正式刊期在该期者（= 简报饼图口径）。
- 输出：每学科一张 PNG + `<标签>_学科贡献率_汇总.png`（网格拼图）+ `<标签>_学院贡献率数据.csv`。
- 学院归属取 C1 第一组的二级单位，用脚本里的 `COLLEGE_MAP` 英文→中文（**必须按校核实**，见 pitfall 18）。

**② 手绘思维导图信息图** — `scripts/build_infographic.py`：

```bash
python3 build_infographic.py <报告.csv> <c1.json> <parsed.json> <标签> <out.png> \
    --org 闽南师范大学 --raw 45 --dropped 4 --outdir <目录>
```

- 中心节点（正式发表/第一单位）+ 六个分支卡：①论文规模 ②分区结构 ③主要合作单位 ④高影响力
  ⑤数据口径 ⑥学科分布与学院贡献率（两栏彩色占比条）。
- 实现：HTML（手绘纸张底纹 + 中文手写字体 + 双线手绘连线）→ Playwright 截图为 PNG（1600×1520 @2x，同目录留 .html 可改）。
- 手写中文字体（无需 sudo）：`~/.local/share/fonts/` 放 ZCOOLKuaiLe-Regular.ttf（站酷快乐体，标题/标签）
  与 MaShanZheng-Regular.ttf（马善政，大标题），再 `fc-cache -f`。下载：
  `https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/zcoolkuaile/ZCOOLKuaiLe-Regular.ttf`
  （jsdelivr 可通，fonts.gstatic.com 常 404；无字体时 Chromium 会用文泉驿黑体，手绘感大减）。
- 版式坑：数字+单位必须禁止换行（`.n` 用 `display:flex` 或 `white-space:nowrap`）；
  卡片高度要按行数留足（合作单位行 16px/line-height 1.5）；卡片坐标不得重叠，画布 1600×1520。

### 阶段 5.5 — 两个必备小步骤（缺了会让交付残缺）

- **分区缓存合并**：`build_report_excel.py --cas` 只吃**一个** json，而分区散在多个 `mnnu_*_cas_raw.json`。
  用 `scripts/merge_cas_cache.py [输出]`（默认 `workspace/mnnu_cas_all.json`）按修改时间新→旧合并、
  先到先得、跳过 error 条目，再把合并结果传给 `--cas`。（letpub 抓取脚本会把 `--cache` 条目写进新 raw，
  所以新月份抓完通常一个 raw 就够，但仍跑一次合并确认覆盖。）8 月实测：合并后 233 刊、失败 0。
- **缺 C1 记录合成第一单位地址**：`scripts/build_c1_full.py <tag>` 读 `mnnu_<tag>_missing_addr.json`
  （全记录页抓的地址段）合成 `mnnu_<tag>_c1_full.json`，供 `college_pies.py` / `build_infographic.py`
  判学院——否则这几篇在两张图里会变成“(无C1)/未识别单位”而丢失。合成格式
  `[第一作者] Minnan Normal Univ, <院系>, ...`。
- 全记录页抓取用 `scripts/missing_addr_generic.py <tag>`（自带 500/SYSTEM ERROR 重试 + 落盘，
  比早期的一次性脚本稳）。
- **“否”要逐条核对后再交付**：打印每条的第一组地址，确认确实是外单位（8 月 7 条：合肥工业大学、
  山东农业大学、四川大学、周口师范学院、重庆文理学院、西安电子科技大学、奥兰科技大学），
  同时反向确认没有同校变体被误判（pitfall 15）。

### 阶段 8.5 — 月度带图简报（表＋饼图合并版 Word，用户口径）

补做多期简报时的四个坑（脚本已修，日后照改）：

- **机构与统计期不能写死**：第一单位列名要用 `f"{org}是否第一单位"`（换机构时会 KeyError）；
  季报的 PD 口径需支持多个前缀（`--period 2026-04,2026-05,2026-06`），只给单个前缀会漏掉整季。
- **饼图文件名要容错**：学科名与饼图文件名可能不一致（`未被2025版收录` 的图叫
  `其他（未被2025版分区表收录）`），直接拼名会缺图（表现为“饼图数 = 学科数 - 1”）。
- **空分区不能直接排序**：`sorted(cnt, key=lambda k: (k[0], k))` 遇空字符串会 IndexError，用 `(k[:1], k)`。
- **口径要按机构统一**：简报口径（第一单位＝本校 且 PD 在期内）在季报与月度之间**不构成加总关系**
  （季度导出与单月检索的 PD 分布不同，同“季度不能按 PD 拆分”）；同一机构历史简报若用了 EA 口径，
  应先核对差异（本例海南师大 8 月：EA 20 篇 vs PD 17 篇）再决定是否重出，不要静默覆盖旧件。

月报/季报 Excel 之外，用户还要一份**带图简报 Word**：左两列是“学科名称 | 论文数量”的分区明细，
**第 3 列按学科纵向合并**，格内放该学科的学院贡献率饼图（表与图合为一体，不是图文分列）。

- **口径（与用户 7 月简报 12 篇完全一致）**：第一单位＝本校 **且 正式刊期 PD 落在统计期**；
  本月提前在线（EA 在本期、PD 在后期）的记录不计入简报，但计入月报 Excel。
  给数前先算三种口径备查：PD 在期 / PD或EA 在期 / 入库 DA 在期（闽南师大 2026-08：15 / 29 / 16）。
- **饼图**：`college_pies.py ... --period <YYYY-MM>`（自动只算 PD 在期者）；输出 `2026年8月_<学科>.png`。
- **文档**：`build_briefing_from_template.py --template <上月简报.docx> --csv <本期报告.csv>
  --period <YYYY-MM> --month 2026年8月 --pie-dir <饼图目录> --out <输出.docx>`。
  做法是**克隆上月简报的行 XML**（保留字体/边框/合并单元格），删掉旧数据行、按本月学科重建
  （分区行＋汇总行），末行“总计”，最后把饼图写进各学科合并列的首行；标题与附注按月份/篇数改写。
- **核验**：`render_docx_preview.py <docx> <out.png>`（mammoth → HTML → Playwright 截图，全页），
  然后用看图核实：题目/副标题/附注月份与篇数、每个学科只有一张饼图且与其行对齐、无空白或错位单元格；
  `dump_docx_blocks.py` 确认行数（学科分区行＋汇总行＋header＋总计）与内嵌图片数。
- **坑**：①标题模板替换写成 f"{month}份"，否则出现“2026年8月月份”；②模板里未被引用的旧图片会留在
  包内（无害，文件略大）；③字节相同的饼图（如两个学科都是“某学院100%”）会被 python-docx 去重，
  media 数量少于学科数是正常的；④用户手里可能有别校/别期的简报草稿，表内数字（如出现“心理学”）
  与本校当期数据不符时不要照抄，按自己复算的口径出表并在交付时说明差异。

### 阶段 9 — 作品门户（在线访问入口，已不再使用 WorkBuddy）

#### 门户口径与多机构（必做）

- **“第一单位”必须再限定“当期正式出版”**：直接统计 `是否第一单位=是` 会把先上线(EA)、正式刊期在别期的论文算进来
  （实测闽南师大 2026年1月：含跨期 38 篇 vs 当期正式出版 11 篇）。门户 KPI 与学院贡献率一律用
  `fu && pin`（`pin` = 正式出版时间以本期 PD 前缀开头），并同时在页面上给出两个口径与文字说明，
  否则对外报数会与月报/简报不一致。核对方法：门户算出的数应与各期简报“总计”逐期相等。
- **多机构门户**：`PERIODS` 每项带 `org` 与 `pfx`，第一单位列名用 `f"{org}是否第一单位"`，
  学院映射按机构加载（`mnnu/jmu/hainan_college_map.json`），否则跨机构的学院归属会全部错位。
- **公开版精简发布**：下载区只挂汇总类（简报 docx / 信息图 png / 贡献率汇总 png），不挂逐篇明细 xlsx；
  `pack_portal.py` 必须先清空 `downloads/`，否则上一版未被引用的文件虽无链接仍可被 URL 直接访问。



#### 公开发布到 GitHub Pages（公开版必须脱敏，三处坑）

1. **脱敏**：公网版先跑 `PORTAL_PUBLIC=1`（隐去作者列与“第一作者”表述），
   再跑 `scripts/deidentify_downloads.py <打包目录>`（删 Excel 的「作者」列、移除「第一作者贡献率」工作表）。
   验证方法：页面 JSON 中不得再有非空 `au`；用不带凭据的 `curl` 拉一个线上 xlsx，确认列头无「作者」。
   逐篇明细含作者姓名属个人信息，不得原样公开；图表/简报/汇总统计可公开。
2. **环境变量要跟着 pack 走**：`pack_portal.py` 内部会**再次调用 build_portal.py**，
   所以 `PORTAL_PUBLIC` / `PORTAL_URL` 必须同时传给 pack，否则打包时重建回暗版（作者列复活）。
3. **必须加 `.nojekyll`**：否则 Pages 构建报 `Page build failed.`（Jekyll 处理中文文件名/下划线资源时挂）；
   加了后重新触发构建（`POST /repos/{o}/{r}/pages/builds`）即成功。
4. **推送**：`scripts/upload_portal.py <本地目录> <仓库子路径> <Pages分支> <Pages目录>`，
   读 `.env` 的 `GITHUB_TOKEN`，经 `GIT_ASKPASS` 传令牌（不进命令行/不走 gh 凭据助手）。
5. **二维码验字节**：发布后用 `scripts/verify_qr.py` 把线上 qr.png 与本地按正式地址重生成的二维码
   **逐字节比对**，确认编码的是正式地址而非本机/临时隧道地址（临时地址会变，绝不能进材料）。

可视化层改由本技能直接生成一个**自包含门户页面 + 本机托管**，作为技能/作品的“访问入口”（带二维码）：

```bash
python3 ~/.hermes/skills/research/wos-monthly-report/scripts/build_portal.py   # 生成 workspace/portal/{index.html,qr.png}
# 托管：用 Hermes 的 background 终端，勿用 nohup/setsid（会被安全策略拦下）
~/.hermes/hermes-agent/venv/bin/python3 -m http.server 8080 --bind 0.0.0.0 --directory $WOS_WORKDIR
```

- 入口地址 `http://localhost:8080/portal/`（WSL2 下 Windows 宿主浏览器可直接打开，已实测 200；
  验证：WSL 内 `curl -s -o /dev/null -w '%{http_code}'` 与 Windows 侧
  `powershell.exe -NoProfile -Command "(Invoke-WebRequest http://localhost:8080/portal/ -UseBasicParsing).StatusCode"` 两边都要 200）。
- **可达性：交付前必须先想清楚，else 用户会报"网址和二维码无法使用"**
  1. 二维码编的是 localhost，**手机扫码永远打不开**（手机上 localhost＝手机自己）。
  2. WSL2 的 8080 默认只在 WSL NAT 内 + 宿主可见，局域网其他设备连不上；`netsh interface portproxy`
     与防火墙规则**需要管理员**，且 connectaddress 要填 WSL IP（`hostname -I`，重启会变）。
  3. 要"可扫码访问"只有两条路：①局域网端口转发（管理员一次配置，二维码改 `http://<Windows 无线网卡 IP>:8080/portal/`）；
     ②发布到公网静态托管（评审/异地扫码用这条，学校服务器或 GitHub/Gitee Pages）。
- 地址可配置：`PORTAL_URL=<地址> python3 scripts/build_portal.py`（等价于第一个命令行参数），默认本机地址；
  换地址只改这一处，全部文案/二维码随之更新。
- **发布（要"可扫码访问的测试链接"就必须走这步）**：`python3 scripts/pack_portal.py <发布地址>` 产出
  `portal_publish/`（index.html＋qr.png＋downloads/，页面里的 `../` 交付物链接自动改写为 downloads/，
  约 2.3MB）→ 原样上传任意静态托管（学校服务器 / GitHub Pages / Gitee Pages / 对象存储静态网站）。

- **给链接前自检**：确认 8080 在监听、`curl` 与 Windows 侧 PowerShell 都返 200、二维码编的地址与实际可访问
  地址一致——三处不一致就是"网址和二维码无法使用"这类反馈的根因。
- 一键启动：`workspace/start_portal.sh`（幂等，已在监听则只提示地址）＋ Windows 桌面 `启动门户.bat`。
  服务是临时进程，WSL/Hermes 重启后需重新拉起，给链接前先确认服务在跑。
- 页面：期次切换（季报/月报 7 期）、指标卡、分区结构、学科分布、学科×学院贡献率（点开折叠）、
  论文明细（搜索＋学科/第一单位筛选）、交付物下载、使用方式与口径说明。无外部 CDN 依赖，离线可用。
- 数据全取自各期报告 CSV + alldb 导出（原始/剔除/正式/第一单位/分区/Top 均为报告口径，不新增口径）。
- 手机扫码需公网发布或 Windows 端口转发（`netsh interface portproxy`，需管理员）；仅本机演示用 localhost 即可。
- 扫码入口更新时重跑 `build_portal.py`（QR 地址写在脚本开头的 `URL`）。

### 阶段 7 — 交付

用 `MEDIA:<绝对路径>` 给出 xlsx（季报/月报）与①②两张图，正文给统计摘要（正式发表条数、第一单位 是/否、
分区分布、Top 篇数）+ 口径说明 + 可选的后续（只筛第一单位=是、加影响因子列等）。

### 多机构复用（同一技能做其他高校）

流水线已机构无关，换学校只换参数，不改脚本：

```bash
P=jmu_aug    # 自定义前缀
python3 scripts/wos_alldb_search_export.py "Jimei University" 2026-08-01 2026-08-31 ${P}_alldb.txt
python3 scripts/woscc_full_export.py      "Jimei University" 2026-08-01 2026-08-31 ${P}_woscc_full.txt
python3 scripts/monthly_analyze_generic.py $P "JIMEI UNIV"      # 机构 token，可给多个
python3 scripts/missing_addr_generic.py    $P                    # 缺 C1 逐条补录（前缀自适应）
python3 scripts/build_c1_full.py           $P                    # 合成 c1_full.json
python3 scripts/journals_generic.py        $P                    # 期刊清单 + 缓存命中/需抓
bash <机构>_cas_run.sh                                          # 分批抓分区（每批 5 刊 + 75s）
python3 scripts/merge_cas_cache.py /tmp/cas_all.json             # 合并所有 cas_raw 缓存
python3 scripts/build_report_excel.py --alldb ${P}_alldb.txt --woscc ${P}_woscc_full.txt \
    --cas /tmp/cas_all.json --org-en "Jimei Univ" --institution 集美大学 --month 2026年8月 \
    --manual ${P}_manual.json --out "集美大学_2026年8月_WOS论文_含中科院分区.xlsx"
python3 scripts/verify_report_generic.py $P "<xlsx>" 集美大学     # 交付前验证
COLLEGE_MAP_JSON=<机构>_college_map.json python3 scripts/college_pies.py "<csv>" ${P}_c1_full.json ${P}_parsed.json "<outdir>" "2026年8月"
COLLEGE_MAP_JSON=<机构>_college_map.json python3 scripts/build_infographic.py "<csv>" ${P}_c1_full.json ${P}_parsed.json "2026年8月" "<out.png>" --org 集美大学 --org-en "Jimei Univ" --raw 155 --dropped 15
```

- **学院映射按机构存 `*_college_map.json`**，用环境变量 `COLLEGE_MAP_JSON=` 叠加到内置映射上
  （`college_pies.py` 与 `build_infographic.py` 同时生效）。第一次做某个学校时先用
  `scripts/dept_inventory.py <prefix> <机构token>` 列出全部二级单位写法，再逐个核实到学院。
- 集美大学已核实映射（2026-08）：Sch Marine Engn=轮机工程学院、Fisheries Coll=水产学院、
  Coll Ocean Food & Biol Engn（含旧名 Coll Food & Biol Engn）=海洋食品与生物工程学院、
  Coll Marine Equipment & Mech Engn=海洋装备与机械工程学院、Sch Ocean Informat Engn=海洋信息工程学院、
  Sch Comp Engn/Coll Comp Engn/Comp Engn Coll=计算机工程学院、Sch Sci=理学院、Nav Coll/Coll Nav=航海学院、
  Coll Harbour & Coastal Engn=港口与海岸工程学院、Sch Phys Educ/Phys Educ Inst=体育学院、
  Coll Arts & Design/Coll Fine Arts & Design=美术与设计学院、Sch Finance & Econ=财经学院、
  Chengyi Coll=诚毅学院（独立学院，仍计第一单位=是，交付时说明）。
- **机构 token 要防误命中**：集美大学用 `JIMEI UNIV`——同月有 `Huaqiao Univ, ... 668 Jimei Ave, Xiamen`
  这种含“Jimei”的**路名**，只用 `JIMEI` 匹配会误判。判定后做反向核查：判“否”的记录里若出现本校字样，
  逐条看原文再定。
- 大校的量级差异：集美大学 2026-08 为 155 原始/140 正式/81 第一单位，需抓分区 93 刊（约 40–60 分钟），
  抓取期间可先用不完整缓存跑一次 `--out /tmp/dryrun.xlsx` 验证管线与 manual 判定。

## Common Pitfalls

1. **All Databases 导出没有 C1/AB**——别指望它直接给第一单位；必须走核心合集 Full Record
   或逐条全文页。（导出后 `'Univ' in row` 自检一眼就知道。）
2. **范围没切 `Records from 1 to N`** → 只得到 50 条且无告警。
3. **表头重复 `AU`** → 用列索引解析，不要 `DictReader`。
4. **默认合集含 Preprint Citation Index** → 结果混入 `PPRN:` 预印本与 `RC:` 记录；
   "正式发表"必须先剔除，并在说明里交代。
5. **第一单位 ≠ 通讯作者单位**：C1 第一组是前者；需要后者时另行判定。
6. **字段标签残留**：用户字段清单可能沿用了上一个任务的机构名（"<别的学校>是否第一单位"），
   要按**本次检索的机构**改名并明确告知，绝不照抄旧名、也绝不因此改检索对象。
7. **HTML/日期控件**：日期用 `type()` 不用 `fill()`；提交用搜索框回车（点 Search 按钮在表单
   未就绪时会跳空白 Search History）。
8. **CARSI 会话 ~10 分钟过期**：过期签名是跳 "Authentication Preference Selection" /
   `Error=shibboleth,ip` / `Server.sessionNotFound`；先重试无 cookie 的 IP 直连，再重登，
   并让"重登 + 需要会话的活儿"在同一个脚本里跑完。
9. **LetPub 限流按 IP**（约 5–9 次快速请求后搜索页无输入框）：新 context 不能解除，只能等
   ≥60s；每条结果**立即落盘**，超时/被杀后从上次成功处续跑（60 刊一轮必然超过 shell 超时）。
10. **分区解析静默出错**（小类 0 条、大类名错乱）很"像"真的——运行时逐刊打印解析结果，
    对可疑条目 dump 原始 block 人工核对。
11. **"某月新增"口径**可在 Publication Date 与入库日期(DA) 之间歧义——先问或明确声明已选哪种。
12. **未被中科院分区表收录的刊**（新刊、中文刊如《生理学报》、仅 Scopus 的刊）在 LetPub 上分区 block 首行就是
    `（没有被2025年的期刊分区表收录，仅供参考）`——`build_report_excel.py` 会把这类刊的分区列留**空白**，
    必须在交付前后处理标注为"未被2025版收录"（并写进说明 sheet），否则下游会当成漏抓/数据错误。
13. **MEDLINE 记录的日期还有第三种格式**：`2026 Jun 11`（空格分隔）。WOS 原生是 `AUG 27 2026`，另一批
    MEDLINE 用 `2026-Aug-27`；三种都要归一化（脚本已支持，若出现新格式先补 `norm_date` 再重跑）。
14. **季报/多年期窗口可直接复用月报脚本**：把 Publication Date 改成 2026-01-01~03-31 即可；
    101 条结果的 `Records from 1 to N` 范围切换正常（脚本自动点 `#radio3-input` 并回读 markTo），
    导出后仍要数非空行数 == N。窗口拉长后 **非论文类型（DT=Correction/Editorial/Meeting Abstract）**
    会出现——这些不是 PPRN/RC，不会被阶段 2 剔掉，必须主动报告（如 1 条勘误）并告诉用户如何筛选。
15. **机构名缩写变体**：WOS 的 C1 里偶尔把 `Minnan Normal Univ` 写成 `Minnan Univ`（如
    “Minnan Univ, Coll Chem Chem Engn & Environm Sci”）。只按 `MINNAN NORMAL UNIV` 匹配会把它错判为
    “否”。看到“否”的机构名与本校**二级学院名吻合**（或记录内邮箱是 `@mnnu.edu.cn`）时，开全记录页
    核对地址列表，确认后用 `--manual` 纠正并写进说明。切勿直接用 `MINNAN UNIV` 做子串匹配——
    `Minnan Univ Sci & Technol`（闽南理工学院）会误命中。
16. **年份型 PD**：部分刊（ELECTRONIC RESEARCH ARCHIVE、AIMS MATHEMATICS、FILOMAT、IEEE ACCESS 等）
    WOS 只给 `PD = 2026`，没有月份。如实保留 `YYYY` 并在说明里交代，不要拿 EA/PY 去凑月份。
17. **全记录页会偶发报错**：MEDLINE 旧记录页可能返回 `HTTP Status 500` 或 WOS `A SYSTEM ERROR HAS
    OCCURRED`，直接重试（隔 10s、最多 4 次）即可成功；重试前不要改用别的口径下结论。
18. **学院映射要核实到"实验室/研究所"层级**（做贡献率饼图/信息图时必碰）。闽南师范大学已核实：
    粒计算及其应用（福建省）重点实验室 → 计算机学院（依据计算机学院官网"本院简介"）；
    生态规划与景观设计研究所、闽台特色园林植物重点实验室 → 生物科学与技术学院（校内研究所一览表）；
    污染监测与控制福建省高校重点实验室 → 化学化工与环境学院；应用心理学研究所/认知与人格重点实验室 → 教育与心理学院。
    另：WOS 地址常被截断（如只剩 `Fujian Prov Univ`）或写成 `Dept Chem & Environm Sci`，要结合同记录其它地址行判断。
19. **篇名→UT 匹配必须归一化**：报告 CSV 回写会改动标题里的引号/空格，直接用篇名查 UT 会漏，
    造成假的"(无C1)/未识别单位"。统一 `re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", 标题.lower())` 后再比对。
20. **门户页面的 JS 与 Python f-string 冲突**：用 Python 生成 HTML 时，JS 模板字符串的 `${x}` 要写成 `${{x}}`，
    且**不要在 JS 模板串里再套模板串**（如 `` `${t?`…`:`''}` ``）——嵌套反引号会让 Python 把 `{t?` 当表达式解析（
    `NameError: name 't' is not defined`）。先把表达式存成变量（`const note = t ? '...' : ''`）再插值。

21. **双月刊期号写法**：`SEP-OCT 2026`（也见 `NOV-DEC 2026`）不属于前述任何格式——`norm_date` 已支持
    （取区间首月，如 `2026-09`）。出表前务必跑 `verify_report_generic.py` 的日期自检（应为 0 处异常），
    否则下游会把 `SEP-OCT 2026` 当脏数据。
22. **LetPub 单刊失败先换 ISSN**：检索命中的是 LetPub 自己的 ISSN，**印本 ISSN 有时查不到**
    （Int J Mol Sci：印本 1661-6596 无结果，电子 1422-0067 命中）。用 `scripts/letpub_one.py
    "<刊名>" <印本ISSN> <raw.json> <电子ISSN,...>` 单刊补抓（带诊断输出，命中即写回缓存）。
23. **大校/大月份必然出现“限流尾巴”**：一次抓 90+ 刊时，最后 8–10 刊会以 `not found` 收场（实为限流）。
    收尾固定加一轮补抓：只取“未抓+error”的子集，每批 **3 刊**、每批前 `sleep 90`（集美大学 2026-08：
    83/93 → 92/93，剩 1 刊用 pitfall 22 手动补）。
24. **WOS 结果计数可能多于可导出记录**：集美大学 2026-08 显示 156 条、Tab 分隔导出稳定为 155 条
    （两次导出的 UT 集合完全一致），不是范围没切——如实写进交付说明，不要为凑数改口径。

25. **季度报告不能靠“导出 PD 字段”拆成单月**：WOS 时间窗匹配的语义与该记录的导出 PD 字段并不一致
    （闽南师大 2026 Q2 导出 109 条里，PD 落在 4—6 月之外的有一批；按 PD 切分只会得到 19+22+33）。
    单月报告一律**各自单月检索**（如 2026-04-01~04-30），并做一次强校验：各月“原始/正式发表/第一单位”
    之和应等于季度报告（Q2 实测 28+36+45=109、28+35+41=104、19+20+31=70），且各月 UT 集合无重叠、
    并集等于季度集合（`scripts/split_quarter_months.py` 的 PD 切分仅可用于粗查，不可用作交付口径）。
26. **缺 C1 与缩写变体要与既有期次保持一致**：同一条记录在季度报告里已判定的（如 `WOS:001745479600001`
    地址写作 `Minnan Univ, Coll Chem Chem Engn & Environm Sci` 判“是”；`MEDLINE:42132239` 判“否”；
    `WOS:001779519300001` 缺 C1 判“是”），单月报告要用 `--manual` 沿用，否则同一篇论文在两处口径不同。
27. **`build_c1_full.py` 取“地址 1”要按行筛选**：全记录页常有“Addresses ⏎ 邮箱 ⏎ Addresses ⏎
    arrow_drop_down ⏎ 1 机构…”结构，直接取 `Addresses` 后第一行会抓到邮箱或作者简介。改为取
    “含 Univ/Coll/Inst/Sch/Lab 等关键词”的第一行，并兼容 `missing_addr.json` 的两种取值
    （dict 带 segment / 纯字符串）。
28. **门户与饼图的学院映射必须是同一份**：`build_portal.py` 里曾复制了一份 COLLEGE_MAP，会绕过
    `COLLEGE_MAP_JSON` 覆盖——统一为从 `college_pies` 导入后合并；`college_of` 对“不是二级单位的写法”
    （城市名 Zhangzhou、国家名、`36 Xianqian Rd`）统一返回“未标注二级单位”，不要当成学院。
29. 新核实的学院写法（闽南师范大学）：`Coll Phys Educ`/`Phys Educ Inst`=体育学院；
    `Coll Biol Sci & Technol`、`Key Lab Landscape Plants Fujian & Taiwan Character`=生物科学与技术学院；
    `Chemical Engineering and Environment`=化学化工与环境学院。

## Verification Checklist

- [ ] 访问方式确认（IP 直连 or CARSI），并把选择写进说明
- [ ] 结果数 N 与导出非空记录数一致（范围已切 1..N）
- [ ] 预印本/RC 已剔除且数量在说明中交代
- [ ] 每条记录都有第一单位判定（C1 缺失的已用全文页补）
- [ ] 每种期刊都有分区或明确标注"未被 2025 版收录"
- [ ] 日期已归一化为 YYYY-MM-DD / YYYY-MM
- [ ] Excel 表头名、行数、是/否与分区计数自洽
- [ ] 说明 sheet 齐全（来源、版本、口径、统计）
- [ ] ①学院贡献率饼图已生成（每学科 PNG + 汇总拼图 + 数据 CSV），学院名已核实到学院层级
- [ ] ②手绘思维导图信息图已生成，图中每个数字与报告/饼图一致（原始数、第一单位数、分区、Top、学科篇数）
- [ ] 交付用 MEDIA: 绝对路径 + 中文统计摘要

## One-Shot Recipes

```bash
# 0) 进入环境
source ~/.hermes/hermes-agent/venv/bin/activate

# 1) All Databases 检索+导出（IP 直连；机构 / 起 / 止 / 输出）
python3 ~/.hermes/skills/research/wos-monthly-report/scripts/wos_alldb_search_export.py \
  "Minnan Normal University" 2026-07-01 2026-07-31 $WOS_WORKDIR/mnnu_jul_alldb.txt

# 2) 核心合集 Full Record 导出（取 C1 判第一单位）
python3 ~/.hermes/skills/research/wos-monthly-report/scripts/woscc_full_export.py \
  "Minnan Normal University" 2026-07-01 2026-07-31 $WOS_WORKDIR/mnnu_jul_woscc.txt

# 3) 分区抓取（复用缓存；可分批：START END）
python3 ~/.hermes/skills/research/wos-monthly-report/scripts/letpub_cas_fetch.py \
  /tmp/journals.json $WOS_WORKDIR/cas_raw.json 0 12

# 4) 生成月报 Excel + CSV
python3 ~/.hermes/skills/research/wos-monthly-report/scripts/build_report_excel.py \
  --alldb alldb.txt --woscc woscc.txt --cas cas_raw.json --org-en "Minnan Normal Univ" \
  --institution "闽南师范大学" --month 2026年7月 --manual manual.json \
  --out $WOS_WORKDIR/闽南师范大学_2026年7月_WOS论文_含中科院分区.xlsx

# 5) 月报附加：学院贡献率饼图 + 手绘信息图（固定两步）
python3 ~/.hermes/skills/research/wos-monthly-report/scripts/college_pies.py \
  "$WOS_WORKDIR/闽南师范大学_2026年6月_WOS论文_含中科院分区.csv" \
  $WOS_WORKDIR/mnnu_jun_c1.json $WOS_WORKDIR/mnnu_jun_parsed.json \
  "$WOS_WORKDIR/月报图表/2026年6月" "2026年6月"
python3 ~/.hermes/skills/research/wos-monthly-report/scripts/build_infographic.py \
  "$WOS_WORKDIR/闽南师范大学_2026年6月_WOS论文_含中科院分区.csv" \
  $WOS_WORKDIR/mnnu_jun_c1.json $WOS_WORKDIR/mnnu_jun_parsed.json \
  "2026年6月" "$WOS_WORKDIR/月报图表/2026年6月/2026年6月_手绘信息图.png" \
  --org 闽南师范大学 --raw 45 --dropped 4 --outdir "$WOS_WORKDIR/月报图表/2026年6月"
```
