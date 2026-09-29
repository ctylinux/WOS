#!/usr/bin/env python3
"""构建《高校WOS论文收录智能分析》作品门户 —— 由 Hermes 技能生成的可视化访问入口。

输出 portal/index.html（自包含，无外部 CDN 依赖）+ portal/qr.png（入口二维码）。
页面含：指标卡 / 分区结构 / 学科分布 / 学科×学院贡献率（可点选）/ 论文明细（可检索）/ 交付物下载。
"""
import csv
import glob
import json
import os
import re
import sys

sys.path.insert(0, "~/.hermes/skills/research/wos-monthly-report/scripts")
from college_pies import MANUAL_COLLEGE, COLLEGE_MAP as _CP_MAP  # noqa: E402

W = os.environ.get("WOS_WORKDIR", os.path.expanduser("~/wos-work"))
OUTDIR = f"{W}/portal"
import os
import sys

# 门户访问地址：可用环境变量 PORTAL_URL 或第一个命令行参数覆盖（默认本机演示地址）
URL = os.environ.get("PORTAL_URL") or (sys.argv[1] if len(sys.argv) > 1
                                       else "http://localhost:8080/portal/")
ORG = "闽南师范大学"

COLLEGE_MAP = {
    "Sch Math & Stat": "数学与统计学院", "Coll Phys & Informat Engn": "物理与信息工程学院",
    "Sch Phys & Informat Engn": "物理与信息工程学院", "Grad Sch Phys & Informat Engn": "物理与信息工程学院",
    "Sch Comp Sci": "计算机学院", "Coll Comp Sci": "计算机学院", "Coll Comp": "计算机学院", "Sch Comp": "计算机学院",
    "Coll Chem Chem Engn & Environm": "化学化工与环境学院", "Coll Chem Chem Engn & Environm Sci": "化学化工与环境学院",
    "Coll Chem & Chem Engn & Environm": "化学化工与环境学院", "Sch Chem Chem Engn & Environm": "化学化工与环境学院",
    "Key Lab Pollut Monitoring & Control": "化学化工与环境学院", "Key Lab Pollut Monitoring & Contr": "化学化工与环境学院",
    "Fujian Prov Univ Key Lab Pollut Monitoring & Contr": "化学化工与环境学院",
    "Fujian Prov Key Lab Modern Analyt Sci & Separat Te": "化学化工与环境学院",
    "Dept Chem & Environm Sci": "化学化工与环境学院", "Dept Chem Chem Engn & Environm": "化学化工与环境学院",
    "Fujian Prov Univ": "化学化工与环境学院",
    "Fujian Key Lab Granular Comp & Applicat": "计算机学院", "Key Lab Granular Comp & Applicat": "计算机学院",
    "Key Lab Data Sci & Intelligence Applicat": "计算机学院",
    "Sch Hist & Geog": "历史地理学院", "Sch Business": "商学院", "Sch Educ & Psychol": "教育与心理学院",
    "Coll Educ & Psychol Sci": "教育与心理学院", "Sch Journalism & Commun": "新闻传播学院",
    "Inst Phys Educ": "体育学院", "Sch Biol Sci & Biotechnol": "生物科学与技术学院",
    "Engn Technol Ctr Mushroom Ind": "生物科学与技术学院", "Biotechnol Res Inst": "生物科学与技术学院",
    "Inst Ecol Planning & Landscape Architecture": "生物科学与技术学院",
    "Fujian Prov Univ Key Lab Fujian & Taiwan Garden Pl": "生物科学与技术学院",
    "Fujian & Taiwan Characterist Fujian Coll & Univ": "生物科学与技术学院",
}
# 叠加技能侧映射（含 COLLEGE_MAP_JSON 覆盖）：门户与饼图/信息图保持同一套学院口径
for _k, _v in _CP_MAP.items():
    COLLEGE_MAP.setdefault(_k, _v)
COLLEGE_MAP.setdefault("Zhangzhou", "未标注二级单位")
COLLEGE_MAP.setdefault("Xiamen", "未标注二级单位")
PY_ORDER = ["材料科学", "地球科学", "法学", "工程技术", "管理学", "化学", "环境科学与生态学",
            "计算机科学", "教育学", "经济学", "军事学", "农林科学", "人文科学", "社会科学",
            "生物学", "数学", "物理与天体物理", "心理学", "药学", "医学", "艺术学", "综合性期刊"]
OTHERS = "其他（未被2025版分区表收录）"
PERIODS = [
    dict(id="q1", tab="2026年1—3月 季报", csv="闽南师范大学_2026年1-3月_WOS论文_含中科院分区.csv",
         alldb="mnnu_q1_alldb.txt", c1="mnnu_q1_c1_full.json", woscc="mnnu_q1_woscc_full.txt"),
    dict(id="q2", tab="2026年4—6月 季报", csv="闽南师范大学_2026年4-6月_WOS论文_含中科院分区.csv",
         alldb="mnnu_q2_alldb.txt", c1="mnnu_q2_c1_full.json", woscc="mnnu_q2_woscc_full.txt"),
    dict(id="m01", tab="2026年1月 月报", csv="闽南师范大学_2026年1月_WOS论文_含中科院分区.csv",
         alldb="mnnu_m01_alldb.txt", c1="mnnu_m01_c1_full.json", woscc="mnnu_m01_woscc_full.txt"),
    dict(id="m02", tab="2026年2月 月报", csv="闽南师范大学_2026年2月_WOS论文_含中科院分区.csv",
         alldb="mnnu_m02_alldb.txt", c1="mnnu_m02_c1_full.json", woscc="mnnu_m02_woscc_full.txt"),
    dict(id="m03", tab="2026年3月 月报", csv="闽南师范大学_2026年3月_WOS论文_含中科院分区.csv",
         alldb="mnnu_m03_alldb.txt", c1="mnnu_m03_c1_full.json", woscc="mnnu_m03_woscc_full.txt"),
    dict(id="m04", tab="2026年4月 月报", csv="闽南师范大学_2026年4月_WOS论文_含中科院分区.csv",
         alldb="mnnu_m04_alldb.txt", c1="mnnu_m04_c1_full.json", woscc="mnnu_m04_woscc_full.txt"),
    dict(id="m05", tab="2026年5月 月报", csv="闽南师范大学_2026年5月_WOS论文_含中科院分区.csv",
         alldb="mnnu_m05_alldb.txt", c1="mnnu_m05_c1_full.json", woscc="mnnu_m05_woscc_full.txt"),
    dict(id="m06", tab="2026年6月 月报", csv="闽南师范大学_2026年6月_WOS论文_含中科院分区.csv",
         alldb="mnnu_jun_alldb.txt", c1="mnnu_jun_c1_full.json", woscc="mnnu_jun_woscc_full.txt"),
    dict(id="m07", tab="2026年7月 月报", csv="闽南师范大学_2026年7月_WOS论文_含中科院分区.csv",
         alldb="mnnu_jul_alldb.txt", c1="mnnu_jul_c1_full.json", woscc="mnnu_jul_woscc_full.txt"),
    dict(id="m08", tab="2026年8月 月报", csv="闽南师范大学_2026年8月_WOS论文_含中科院分区.csv",
         alldb="mnnu_aug_alldb.txt", c1="mnnu_aug_c1_full.json", woscc="mnnu_aug_woscc_full.txt"),
]


def norm(t):
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (t or "").lower())


def read_indexed(path):
    lines = open(path, encoding="utf-8-sig").readlines()
    header = lines[0].rstrip("\n").split("\t")
    idx = {}
    for i, n in enumerate(header):
        if n and n not in idx:
            idx[n] = i
    out = []
    for line in lines[1:]:
        if not line.strip():
            continue
        c = line.rstrip("\n").split("\t")
        c += [""] * (len(header) - len(c))
        out.append(c)
    return idx, out


def c1_map_from_woscc(path):
    idx, rows = read_indexed(path)
    return {c[idx["UT"]]: c[idx["C1"]] for c in rows}


def college_of(ut, c1):
    if ut in MANUAL_COLLEGE:
        return MANUAL_COLLEGE[ut]
    m = re.match(r"^\[([^\]]*)\]\s*(.*?)(?:\s*;\s*\[|$)", c1.get(ut, "") or "")
    if not m:
        return "未识别单位"
    parts = [x.strip() for x in m.group(2).split(",")]
    raw = parts[1] if len(parts) > 1 else parts[0]
    if re.match(r"^\d+\s+\w", raw) or re.match(r"^[A-Z][a-z]+ \d{5}", raw) or re.match(r"^.+\d{5}$", raw):
        return "未标注二级单位"
    return COLLEGE_MAP.get(raw, raw)


def build_period(p):
    idx, rows = read_indexed(f"{W}/{p['alldb']}")
    formal_ut = set()
    dropped = 0
    raw = len(rows)
    ti2ut = {}
    for c in rows:
        ut = c[idx["UT"]]
        ti2ut[norm(c[idx["TI"]])] = ut
        if ut.startswith(("WOS:", "MEDLINE:")):
            formal_ut.add(ut)
        else:
            dropped += 1
    c1 = {}
    if p.get("c1") and os.path.exists(f"{W}/{p['c1']}"):
        c1 = json.load(open(f"{W}/{p['c1']}", encoding="utf-8"))
    elif os.path.exists(f"{W}/{p['woscc']}"):
        c1 = c1_map_from_woscc(f"{W}/{p['woscc']}")
    rows_csv = list(csv.DictReader(open(f"{W}/{p['csv']}", encoding="utf-8-sig")))
    fu = f"{ORG}是否第一单位"
    recs = []
    for r in rows_csv:
        ut = ti2ut.get(norm(r.get("篇名", "")), "")
        subj = r.get("中科院大类学科") or OTHERS
        if subj == "未被2025版收录":
            subj = OTHERS
        recs.append(dict(ut=ut, ti=r.get("篇名", ""), au=r.get("作者", ""), so=r.get("期刊来源", ""),
                         su=subj, q=r.get("大类分区", ""), top=(r.get("Top期刊") == "是"),
                         fu=(r.get(fu) == "是"), da=r.get("入库时间", ""), pd=r.get("正式出版时间", ""),
                         ea=r.get("EA时间", ""), col=college_of(ut, c1)))
    return dict(id=p["id"], tab=p["tab"], raw=raw, dropped=dropped, records=recs,
                formal=len(formal_ut) if formal_ut else len(recs))


data = {}
for p in PERIODS:
    try:
        data[p["id"]] = build_period(p)
        d = data[p["id"]]
        yes = sum(1 for r in d["records"] if r["fu"])
        print(f"  {d['tab']}: 原始 {d['raw']} → 正式 {len(d['records'])} | 第一单位 {yes} "
              f"| 未识别学院 {sum(1 for r in d['records'] if r['col'] in ('未识别单位','未标注二级单位') and r['fu'])}")
    except Exception as e:
        print(f"  [skip] {p['id']}: {e}")

FILES = [
    ("闽南师范大学_2026年1-3月_WOS论文_含中科院分区.xlsx", "1—3月季报 明细表（Excel）"),
    ("闽南师范大学_2026年4-6月_WOS论文_含中科院分区.xlsx", "4—6月季报 明细表（Excel）"),
    ("闽南师范大学_2026年1-3月_学科贡献率统计.xlsx", "1—3月学科贡献率统计（学科×学院＋第一作者）"),
    ("2026年1-3月闽南师范大学Web of Science收录论文简报（带图）.docx", "1—3月 带图简报（Word）"),
    ("2026年7月闽南师范大学Web of Science收录论文简报（带图）.docx", "7月 带图简报（Word）"),
    ("月报图表/2026年6月/2026年6月_学科贡献率_汇总.png", "6月 各学院对学科贡献率饼图（汇总）"),
    ("月报图表/2026年6月/2026年6月_手绘信息图.png", "6月 手绘思维导图信息图"),
    ("闽南师范大学_2026年4月_WOS论文_含中科院分区.xlsx", "4月月报 明细表（Excel）"),
    ("闽南师范大学_2026年5月_WOS论文_含中科院分区.xlsx", "5月月报 明细表（Excel）"),
    ("闽南师范大学_2026年8月_WOS论文_含中科院分区.xlsx", "8月月报 明细表（Excel）"),
    ("2026年8月闽南师范大学Web of Science收录论文简报（带图）.docx", "8月 带图简报（Word，表＋饼图合一）"),
    ("月报图表/2026年4月/2026年4月_学科贡献率_汇总.png", "4月 各学院对学科贡献率饼图（汇总）"),
    ("月报图表/2026年4月/2026年4月_手绘信息图.png", "4月 手绘思维导图信息图"),
    ("月报图表/2026年5月/2026年5月_学科贡献率_汇总.png", "5月 各学院对学科贡献率饼图（汇总）"),
    ("月报图表/2026年5月/2026年5月_手绘信息图.png", "5月 手绘思维导图信息图"),
    ("月报图表/2026年8月/2026年8月_学科贡献率_汇总.png", "8月 各学院对学科贡献率饼图（汇总）"),
    ("月报图表/2026年8月/2026年8月_手绘信息图.png", "8月 手绘思维导图信息图"),
]
deliv = [(f, t) for f, t in FILES if os.path.exists(f"{W}/{f}")]

payload = json.dumps({"org": ORG, "periods": data}, ensure_ascii=False, separators=(",", ":"))
deliv_html = "".join(
    f'<a class="dl" href="../{f}" target="_blank"><b>{t}</b><span>{f.split("/")[-1]}</span></a>'
    for f, t in deliv)

html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>高校WOS论文收录智能分析月报系统 · 访问入口</title>
<style>
 :root{{--ink:#12233b;--blue:#0E9BD3;--org:#E57030;--grn:#4CA52C;--gold:#FFC000;--gray:#A5A5A5;--line:#dfe6ef}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:#f4f7fb;color:var(--ink);font:15px/1.7 "Microsoft YaHei","WenQuanYi Zen Hei",sans-serif}}
 .wrap{{max-width:1180px;margin:0 auto;padding:22px}}
 header{{background:linear-gradient(135deg,#0d2b45,#1f6f9a);color:#fff;padding:30px 0 26px}}
 header .wrap{{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;flex-wrap:wrap}}
 h1{{margin:0 0 6px;font-size:27px;letter-spacing:1px}}
 .sub{{opacity:.88;font-size:14px}}
 .badge{{display:inline-block;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.35);
   border-radius:999px;padding:3px 12px;font-size:13px;margin-top:10px}}
 .qr{{background:#fff;padding:8px;border-radius:10px;text-align:center}}
 .qr img{{width:120px;height:120px;display:block}}
 .qr span{{color:#44607a;font-size:11px}}
 h2{{font-size:19px;margin:26px 0 12px;padding-left:10px;border-left:5px solid var(--blue)}}
 .card{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 18px;
   box-shadow:0 2px 10px rgba(18,35,59,.05)}}
 .tabs{{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 16px}}
 .tabs button{{border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:999px;
   padding:7px 15px;font-size:14px;cursor:pointer}}
 .tabs button.on{{background:var(--blue);border-color:var(--blue);color:#fff;font-weight:700}}
 .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
 .kpi{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
 .kpi i{{display:block;color:#6b7d94;font-style:normal;font-size:13px}}
 .kpi b{{font-size:30px;color:var(--blue);line-height:1.25}}
 .kpi s{{text-decoration:none;color:#8194a8;font-size:12px;margin-left:4px}}
 .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
 @media(max-width:900px){{.grid2{{grid-template-columns:1fr}}}}
 .bar{{display:flex;align-items:center;gap:10px;margin:6px 0}}
 .bar .nm{{width:112px;font-size:14px;color:#33465c}}
 .bar .tr{{flex:1;height:16px;background:#eef3f9;border-radius:8px;overflow:hidden}}
 .bar .tr i{{display:block;height:100%}}
 .bar .vl{{width:78px;text-align:right;font-size:13px;color:#5b6f86}}
 .subj{{border-bottom:1px dashed #e7edf5;padding:9px 0}}
 .subj:last-child{{border-bottom:0}}
 .subj .hd{{display:flex;justify-content:space-between;cursor:pointer;font-size:15px}}
 .subj .hd:hover{{color:var(--blue)}}
 .subj .bd{{display:none;padding:8px 0 4px}}
 .subj.open .bd{{display:block}}
 .subj .seg{{display:flex;height:14px;border-radius:7px;overflow:hidden;margin:6px 0}}
 .lg{{font-size:12.5px;color:#5b6f86}}
 table{{width:100%;border-collapse:collapse;font-size:13.5px}}
 th,td{{border-bottom:1px solid var(--line);padding:8px 9px;text-align:left;vertical-align:top}}
 th{{background:#eef4fa;font-weight:700;color:#2b4257;position:sticky;top:0}}
 tr.y td:nth-child(2){{background:#eaf7ea;color:#2f7a2f;font-weight:700;text-align:center}}
 tr.n td:nth-child(2){{background:#fdeeee;color:#a33;font-weight:700;text-align:center}}
 .tools{{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}}
 .tools input,.tools select{{padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:14px}}
 .tblbox{{max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:10px;background:#fff}}
 .dl{{display:flex;justify-content:space-between;gap:12px;align-items:center;text-decoration:none;
   color:var(--ink);background:#fff;border:1px solid var(--line);border-radius:10px;padding:11px 14px;margin:8px 0}}
 .dl:hover{{border-color:var(--blue);box-shadow:0 2px 8px rgba(14,155,211,.16)}}
 .dl span{{color:#7b8ea3;font-size:12px}}
 code{{background:#eef3f9;padding:2px 7px;border-radius:6px;font-size:13px}}
 footer{{color:#6b7d94;font-size:13px;text-align:center;padding:26px 0 40px}}
</style></head><body>
<header><div class="wrap">
  <div>
    <h1>高校WOS论文收录智能分析月报系统</h1>
    <div class="sub">{ORG}图书馆 · 按月／按季自动产出收录统计、分区结构、学院贡献率与信息图</div>
    <div class="badge">可视化层由 Hermes Agent 技能直接生成（不再依赖 WorkBuddy）</div>
  </div>
  <div class="qr"><img src="qr.png" alt="入口二维码"><span>扫码／打开链接访问</span></div>
</div></header>

<div class="wrap">
  <h2>一、在线看板</h2>
  <div class="tabs" id="tabs"></div>
  <div class="kpis" id="kpis"></div>

  <div class="grid2" style="margin-top:16px">
    <div class="card"><h2 style="margin-top:0">分区结构</h2><div id="quart"></div></div>
    <div class="card"><h2 style="margin-top:0">学科分布</h2><div id="subjects"></div></div>
  </div>

  <div class="card" style="margin-top:16px">
    <h2 style="margin-top:0">学科 × 学院贡献率<span class="lg">　（点击学科展开；贡献率＝该学院第一作者论文数 ÷ 该学科论文总数）</span></h2>
    <div id="contrib"></div>
  </div>

  <h2>二、论文明细</h2>
  <div class="tools">
    <input id="q" placeholder="搜索篇名／作者／期刊" style="min-width:260px">
    <select id="fsu"></select>
    <select id="ffu"><option value="">全部</option><option value="y">仅第一单位=本校</option><option value="n">仅非第一单位</option></select>
    <span class="lg" id="cnt"></span>
  </div>
  <div class="tblbox"><table id="tbl"><thead><tr>
    <th style="width:44px">#</th><th style="width:64px">第一单位</th><th>篇名</th><th style="width:190px">作者</th>
    <th style="width:170px">期刊来源</th><th style="width:96px">大类学科</th><th style="width:64px">分区</th>
    <th style="width:54px">Top</th><th style="width:86px">入库</th><th style="width:86px">正式出版</th></tr></thead>
    <tbody></tbody></table></div>

  <h2>三、交付物下载</h2>
  <div class="card">{deliv_html}</div>

  <h2>四、使用方式</h2>
  <div class="card">
    <p style="margin-top:0">在 Hermes Agent 中一句自然语言指令即可复跑全流程：</p>
    <p><code>用高校WOS月报技能，制作闽南师范大学2026年X月WOS月报</code></p>
    <p class="lg">流程：窗口检索 → 剔除预印本/非期刊 → 核心合集取 C1 → 第一单位三级判定 → 期刊去重查中科院分区
    → 生成明细表与说明 → 验证计数 → 生成学院贡献率饼图 → 生成手绘思维导图信息图。</p>
    <p class="lg">口径：第一单位＝WOS 记录 C1 地址第一组（第一作者单位）；分区＝中科院文献情报中心期刊分区表 2025 年 3 月升级版；
    数据源＝Web of Science 所有数据库（校园网 IP 直连）。</p>
  </div>
</div>
<footer>本页面由 Hermes Agent「wos-monthly-report」技能自动生成 · 数据来源 Web of Science · 统计对象为公开发表的学术成果</footer>

<script>
const DATA = {payload};
const C = ['#0E9BD3','#E57030','#4CA52C','#FFC000','#A5A5A5','#7030A0','#2E86AB','#C0392B'];
let cur = Object.keys(DATA.periods)[0];
const $ = s => document.querySelector(s);
const esc = s => (s||'').replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}})[c]);

function subjectOrder(recs) {{
  const m = {{}}; recs.forEach(r => m[r.su] = (m[r.su]||0)+1);
  return Object.keys(m).sort((a,b) => {{
    const oa = a=== "{OTHERS}" ? 1 : 0, ob = b=== "{OTHERS}" ? 1 : 0;
    if (oa!==ob) return oa-ob;
    if (m[b]!==m[a]) return m[b]-m[a];
    const pa = {json.dumps(PY_ORDER, ensure_ascii=False)}.indexOf(a), pb = {json.dumps(PY_ORDER, ensure_ascii=False)}.indexOf(b);
    return (pa<0?99:pa)-(pb<0?99:pb);
  }});
}}

function renderTabs() {{
  $('#tabs').innerHTML = Object.values(DATA.periods).map(p =>
    `<button class="${{p.id===cur?'on':''}}" data-id="${{p.id}}">${{p.tab}}</button>`).join('');
  document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => {{ cur = b.dataset.id; render(); }});
}}

function render() {{
  const P = DATA.periods[cur], recs = P.records;
  const yes = recs.filter(r => r.fu).length;
  const q = {{}}; recs.forEach(r => {{ const k = r.q || '未被2025版收录'; q[k] = (q[k]||0)+1; }});
  const top = recs.filter(r => r.top).length;
  const su = subjectOrder(recs);
  const qs = ['1区','2区','3区','4区','未被2025版收录'].filter(k => q[k]);
  $('#kpis').innerHTML = [
    ['原始检索', P.raw, '条'], ['正式发表', recs.length, '篇'], ['第一单位=本校', yes, '篇'],
    ['1 区', q['1区']||0, '篇'], ['Top 期刊', top, '篇'], ['学科数', su.length, '个'], ['来源期刊', new Set(recs.map(r=>r.so)).size, '种']
  ].map(([a,b,c]) => `<div class="kpi"><i>${{a}}</i><b>${{b}}</b><s>${{c}}</s></div>`).join('');

  const qcol = {{'1区':'#0E9BD3','2区':'#E57030','3区':'#4CA52C','4区':'#FFC000','未被2025版收录':'#A5A5A5'}};
  $('#quart').innerHTML = qs.map(k => `<div class="bar"><span class="nm">${{k}}</span>
     <span class="tr"><i style="width:${{100*q[k]/recs.length}}%;background:${{qcol[k]}}"></i></span>
     <span class="vl">${{q[k]}} 篇 · ${{(100*q[k]/recs.length).toFixed(0)}}%</span></div>`).join('');

  $('#subjects').innerHTML = su.map(k => {{
    const n = recs.filter(r => r.su===k).length;
    const t = recs.filter(r => r.su===k && r.top).length;
    const topNote = t ? (' · Top ' + t) : '';
    return `<div class="bar"><span class="nm">${{k}}</span>
      <span class="tr"><i style="width:${{100*n/recs.length}}%;background:var(--blue)"></i></span>
      <span class="vl">${{n}} 篇${{topNote}}</span></div>`;
  }}).join('');

  $('#contrib').innerHTML = su.map(k => {{
    const rows = recs.filter(r => r.su===k && r.fu);
    if (!rows.length) return `<div class="subj"><div class="hd"><span>${{k}}</span><span class="lg">本期无本校第一单位论文</span></div></div>`;
    const m = {{}}; rows.forEach(r => m[r.col] = (m[r.col]||0)+1);
    const items = Object.entries(m).sort((a,b) => b[1]-a[1]);
    const seg = items.map(([c,v],i) => `<i style="width:${{100*v/rows.length}}%;background:${{C[i%C.length]}}"></i>`).join('');
    const lg = items.map(([c,v],i) => `<span class="lg"><b style="display:inline-block;width:10px;height:10px;background:${{C[i%C.length]}};border-radius:2px;margin-right:4px"></b>${{esc(c)}} ${{v}} 篇（${{(100*v/rows.length).toFixed(0)}}%）</span>`).join('<br>');
    return `<div class="subj"><div class="hd"><span><b>${{k}}</b> <span class="lg">${{rows.length}} 篇</span></span>
      <span class="lg">${{items.length}} 个学院 ▾</span></div>
      <div class="bd"><div class="seg">${{seg}}</div>${{lg}}</div></div>`;
  }}).join('');
  document.querySelectorAll('#contrib .subj .hd').forEach(h => h.onclick = () => h.parentElement.classList.toggle('open'));

  $('#fsu').innerHTML = '<option value="">全部学科</option>' + su.map(k => `<option>${{k}}</option>`).join('');
  fillTable();
}}

function fillTable() {{
  const P = DATA.periods[cur];
  const kw = $('#q').value.trim().toLowerCase(), su = $('#fsu').value, fu = $('#ffu').value;
  let rows = P.records.filter(r =>
    (!kw || (r.ti+r.au+r.so).toLowerCase().includes(kw)) && (!su || r.su===su) &&
    (!fu || (fu==='y' ? r.fu : !r.fu)));
  $('#cnt').textContent = `命中 ${{rows.length}} 篇`;
  const show = rows.slice(0, 400);
  $('#tbl tbody').innerHTML = show.map((r,i) => `<tr class="${{r.fu?'y':'n'}}">
    <td>${{i+1}}</td><td>${{r.fu?'是':'否'}}</td><td>${{esc(r.ti)}}</td><td>${{esc(r.au)}}</td>
    <td>${{esc(r.so)}}</td><td>${{esc(r.su)}}</td><td>${{esc(r.q)}}</td><td>${{r.top?'是':''}}</td>
    <td>${{esc(r.da)}}</td><td>${{esc(r.pd)}}</td></tr>`).join('')
    + (rows.length>show.length ? `<tr><td colspan="10" class="lg">仅显示前 400 条，请用搜索或筛选缩小范围</td></tr>` : '');
}}
['q','fsu','ffu'].forEach(id => document.addEventListener('DOMContentLoaded', () => {{
  document.getElementById(id).addEventListener('input', fillTable);
}}));
renderTabs(); render();
</script></body></html>"""

os.makedirs(OUTDIR, exist_ok=True)
open(f"{OUTDIR}/index.html", "w", encoding="utf-8").write(html)
print("[OK] portal/index.html", os.path.getsize(f"{OUTDIR}/index.html"))

import segno
qr = segno.make(URL, error="m")
qr.save(f"{OUTDIR}/qr.png", scale=8, border=2)
print("[OK] portal/qr.png for", URL)
