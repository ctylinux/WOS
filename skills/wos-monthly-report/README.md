# 高校学科发展智能支持平台（Hermes 技能）

> 原名／别名：高校 WOS 论文收录智能分析月报系统；技术标识 `wos-monthly-report`。

把「Web of Science 检索导出 → 清洗 → 中科院分区 → 学院/学者贡献率 → 报表与图表」整条
流水线固化为可复用的 Hermes 技能：换一所学校只改参数（机构英文 token、学院映射文件），
脚本不重写。适用于高校图书馆的论文收录统计月报/季报、学科贡献分析、大赛与汇报材料制作。

## 它能产出什么

| 交付物 | 说明 |
|---|---|
| 月报/季报 Excel + CSV | 逐篇明细：题名、期刊、分区（大类/小类/Top）、第一单位判定、学院归属 |
| 带图简报 Word | 学科 → 论文数 → 按学科纵向合并的饼图，与明细同源 |
| 学科 × 学院贡献率饼图包 | 每学院 3D 饼图 + 汇总图 + CSV，供汇报与门户使用 |
| 手绘风格信息图 | 一页看清总量、第一单位数、分区结构、Top 期刊、学科分布 |
| 作品门户网页 | 自包含 HTML（零 CDN）+ 二维码 + 交付物下载索引 |

## 安装

```bash
# 方式一：从 GitHub 仓库安装（把 <owner>/<repo> 换成实际仓库）
hermes skills tap add <owner>/<repo>
hermes skills search wos
hermes skills install <owner>/<repo>/wos-monthly-report

# 方式二：直接克隆到技能目录
git clone https://github.com/<owner>/<repo>.git ~/.hermes/skills/research/wos-monthly-report

# 方式三：从单个 SKILL.md 链接安装（技能中心/静态站托管）
hermes skills install https://<你的域名>/wos-monthly-report/SKILL.md
```

## 依赖

```bash
python3 -m pip install -r requirements.txt
playwright install chromium          # 抓取分区、渲染门户预览需要
```

中文字体：Linux 下建议安装 `fonts-wqy-zenhei`（或设置 `WOS_FONT=/path/to/font.ttc`）。

## 快速开始

```bash
export WOS_WORKDIR=~/wos-work        # 所有中间产物与交付物的目录（默认 ~/wos-work）
mkdir -p $WOS_WORKDIR && cd $WOS_WORKDIR

# 1) 检索导出（WOS 所有数据库；字段 Address = "<机构英文名>"，PD 窗口）
python3 <skill>/scripts/wos_alldb_search_export.py ...

# 2) 清洗 + 第一单位判定 + 汇总期刊清单
python3 <skill>/scripts/monthly_analyze_generic.py <前缀> "EXAMPLE UNIV"
python3 <skill>/scripts/journals_generic.py <前缀>

# 3) 抓中科院分区（LetPub）并合并缓存
python3 <skill>/scripts/letpub_cas_fetch.py <前缀>_journals_miss.json <前缀>_cas_raw.json
python3 <skill>/scripts/merge_cas_cache.py <前缀>_cas_all.json <前缀>_cas_raw.json ...

# 4) 出表 → 验证 → 图表 → 信息图 → 门户
python3 <skill>/scripts/build_report_excel.py ...
python3 <skill>/scripts/verify_report_generic.py <前缀> "<xlsx>" <机构中文名>
python3 <skill>/scripts/college_pies.py --period <期间>
python3 <skill>/scripts/build_infographic.py ...
python3 <skill>/scripts/build_portal.py --periods ... --url "$PORTAL_URL"
```

完整流程、12 个标准阶段、22 个坑位与各机构复用要点见 **SKILL.md**。

## 数据与合规（重要）

本包**只包含代码与文档，不包含任何数据库导出数据**。使用时请注意：

- WOS / Scopus 等数据库的导出数据受数据库商条款约束，**不得再分发**；
- 中科院分区表数据（经 LetPub 等平台转引）为第三方版权数据，请勿随包公开传播；
- 论文题名、作者姓名、邮箱等属于个人信息，公开演示请使用脱敏或合成样例；
- 学院/学者贡献率结论请在机构内部使用，对外发布前删除作者姓名。

## 许可

- 代码：MIT（见 LICENSE）
- 文档与图表模板：CC BY 4.0

## 免责声明

本技能按"现状"提供，作者不对统计结果的法律或考核用途作出保证；分区数据以期刊分区表官方
发布为准，抓取结果仅供参考，正式对外数据请与官方平台核对。
