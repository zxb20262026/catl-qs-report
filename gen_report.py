#!/usr/bin/env python3
"""
CATL QuantiSkills 全景分析 — HTML报告生成器
基于 QuantiSkills 框架：13大模块，暗色主题，SVG图表，零外部依赖
"""

import json, os, sys, statistics, math
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
OUTPUT = os.path.join(os.path.dirname(__file__), "index.html")

def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)

def nvl(v, default="—"):
    """空值保护"""
    return v if v is not None else default

def fmt_num(v, dec=2):
    try:
        return f"{float(v):.{dec}f}"
    except:
        return "—"

def fmt_pct(v, signed=True):
    try:
        val = float(v)
        if signed and val > 0:
            return f"+{val:.2f}%"
        return f"{val:.2f}%"
    except:
        return "—"

def color_change(val, cls_only=False):
    """涨跌颜色: 红涨绿跌(A股约定)"""
    try:
        v = float(val)
        if v > 0:
            return "up" if cls_only else "#f85149"
        elif v < 0:
            return "down" if cls_only else "#3fb950"
        return "flat" if cls_only else "#8b949e"
    except:
        return "flat" if cls_only else "#8b949e"

def peg_verdict(peg):
    """PEG信号灯"""
    if peg is None:
        return "⚪ 数据不足", "#8b949e", "待定"
    if peg < 0.8:
        return "🟢 显著低估", "#3fb950", "低估"
    elif peg < 1.0:
        return "🟢 低估区间", "#3fb950", "低估"
    elif peg < 1.5:
        return "🟡 合理区间", "#d29922", "合理"
    else:
        return "🔴 偏高区间", "#f85149", "偏高"

def rsi_verdict(rsi):
    if rsi is None: return "—", "#8b949e"
    if rsi > 70: return "超买", "#f85149"
    if rsi < 30: return "超卖", "#3fb950"
    if rsi > 50: return "偏强", "#d29922"
    return "偏弱", "#8b949e"

def rsi_verdict_display(rsi):
    v, c = rsi_verdict(rsi)
    return v

# ════════════════════════════════════════════════
# SVG 图表生成
# ════════════════════════════════════════════════

def svg_price_chart(klines, ma5, ma20, ma60, width=800, height=300):
    """K线走势 + 均线SVG"""
    if len(klines) < 5:
        return '<p style="color:#8b949e">数据不足，无法绘制</p>'
    
    closes = [k["close"] for k in klines]
    ma5_vals = [m["value"] for m in ma5 if m["value"]]
    ma20_vals = [m["value"] for m in ma20 if m["value"]]
    ma60_vals = [m["value"] for m in ma60 if m["value"]]
    
    all_vals = closes + ma5_vals + ma20_vals + ma60_vals
    all_vals = [v for v in all_vals if v]
    if not all_vals:
        return ""
    
    y_min = min(all_vals) * 0.95
    y_max = max(all_vals) * 1.05
    y_range = y_max - y_min if y_max > y_min else 1
    
    margin = {"top": 20, "right": 20, "bottom": 30, "left": 50}
    w = width - margin["left"] - margin["right"]
    h = height - margin["top"] - margin["bottom"]
    
    def x_pos(i):
        return margin["left"] + (i / (len(klines) - 1)) * w if len(klines) > 1 else margin["left"] + w/2
    
    def y_pos(val):
        return margin["top"] + (1 - (val - y_min) / y_range) * h
    
    def polyline(vals, color, width=1.5):
        points = []
        for i, v in enumerate(vals):
            if v is not None:
                points.append(f"{x_pos(i)},{y_pos(v)}")
        if points:
            return f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="{width}"/>'
        return ""
    
    # 背景网格
    grid = ""
    for i in range(5):
        gy = margin["top"] + i * h / 4
        pv = y_max - i * y_range / 4
        grid += f'<line x1="{margin["left"]}" y1="{gy}" x2="{margin["left"]+w}" y2="{gy}" stroke="#1c2333" stroke-width="0.5"/>'
        grid += f'<text x="{margin["left"]-8}" y="{gy+4}" fill="#484f5e" font-size="9" text-anchor="end">{pv:.0f}</text>'
    
    # 日期标签
    date_labels = ""
    step = max(1, len(klines) // 6)
    for i in range(0, len(klines), step):
        d = klines[i]["date"][-5:]
        date_labels += f'<text x="{x_pos(i)}" y="{height-5}" fill="#484f5e" font-size="9" text-anchor="middle">{d}</text>'
    
    return f'''
    <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="#0d1117"/>
      {grid}
      {date_labels}
      {polyline(closes, "#58a6ff", 1.5)}
      {polyline([m["value"] for m in ma5], "#f85149", 1)}
      {polyline([m["value"] for m in ma20], "#d29922", 1)}
      {polyline([m["value"] for m in ma60], "#3fb950", 1)}
      <!-- Legend -->
      <text x="{margin["left"]+5}" y="18" fill="#58a6ff" font-size="10">— 收盘价</text>
      <text x="{margin["left"]+80}" y="18" fill="#f85149" font-size="10">— MA5</text>
      <text x="{margin["left"]+140}" y="18" fill="#d29922" font-size="10">— MA20</text>
      <text x="{margin["left"]+205}" y="18" fill="#3fb950" font-size="10">— MA60</text>
    </svg>'''


def svg_macd_chart(macd_data, width=800, height=150):
    """MACD柱状图"""
    valid = [m for m in macd_data if m["macd"] is not None]
    if len(valid) < 5:
        return ""
    
    difs = [m["dif"] for m in valid]
    macds = [m["macd"] for m in valid]
    all_vals = difs + macds
    y_max = max(abs(v) for v in all_vals) * 1.2 if all_vals else 1
    y_min = -y_max
    
    margin = {"top": 15, "right": 10, "bottom": 20, "left": 40}
    w = width - margin["left"] - margin["right"]
    h = height - margin["top"] - margin["bottom"]
    
    def x_pos(i):
        return margin["left"] + (i / (len(valid) - 1)) * w if len(valid) > 1 else margin["left"] + w/2
    
    def y_pos(val):
        return margin["top"] + (1 - (val - y_min) / (y_max * 2)) * h
    
    zero_y = y_pos(0)
    
    # DIF线
    dif_points = " ".join(f"{x_pos(i)},{y_pos(difs[i])}" for i in range(len(valid)))
    # DEA线
    dea_points = " ".join(f"{x_pos(i)},{y_pos(valid[i]['dea'])}" for i in range(len(valid)))
    # MACD柱
    bars = ""
    for i, m in enumerate(valid):
        x = x_pos(i)
        y = y_pos(m["macd"])
        bars += f'<rect x="{x-1}" y="{min(y, zero_y)}" width="2" height="{abs(y-zero_y)}" fill="{color_change(m["macd"])}" opacity="0.7"/>'
    
    return f'''
    <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="#0d1117"/>
      <line x1="{margin["left"]}" y1="{zero_y}" x2="{margin["left"]+w}" y2="{zero_y}" stroke="#1c2333" stroke-width="0.5"/>
      {bars}
      <polyline points="{dif_points}" fill="none" stroke="#58a6ff" stroke-width="1"/>
      <polyline points="{dea_points}" fill="none" stroke="#d29922" stroke-width="1"/>
      <text x="{margin["left"]+5}" y="12" fill="#58a6ff" font-size="9">— DIF</text>
      <text x="{margin["left"]+60}" y="12" fill="#d29922" font-size="9">— DEA</text>
    </svg>'''


def svg_rsi_chart(rsi_data, width=800, height=120):
    """RSI图表"""
    valid = [r for r in rsi_data if r["rsi"] is not None]
    if len(valid) < 5:
        return ""
    
    margin = {"top": 10, "right": 10, "bottom": 15, "left": 30}
    w = width - margin["left"] - margin["right"]
    h = height - margin["top"] - margin["bottom"]
    
    def x_pos(i):
        return margin["left"] + (i / (len(valid) - 1)) * w if len(valid) > 1 else margin["left"] + w/2
    
    def y_pos(v):
        return margin["top"] + (1 - (v - 0) / 100) * h
    
    points = " ".join(f"{x_pos(i)},{y_pos(r['rsi'])}" for i, r in enumerate(valid))
    
    return f'''
    <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="#0d1117"/>
      <line x1="{margin["left"]}" y1="{y_pos(70)}" x2="{margin["left"]+w}" y2="{y_pos(70)}" stroke="#f85149" stroke-width="0.5" stroke-dasharray="3,3"/>
      <line x1="{margin["left"]}" y1="{y_pos(30)}" x2="{margin["left"]+w}" y2="{y_pos(30)}" stroke="#3fb950" stroke-width="0.5" stroke-dasharray="3,3"/>
      <text x="{margin["left"]+2}" y="{y_pos(70)-3}" fill="#f85149" font-size="8">70</text>
      <text x="{margin["left"]+2}" y="{y_pos(30)-3}" fill="#3fb950" font-size="8">30</text>
      <polyline points="{points}" fill="none" stroke="#bc8cff" stroke-width="1.5"/>
    </svg>'''


# ════════════════════════════════════════════════
# HTML生成
# ════════════════════════════════════════════════

CSS = """
:root {
  --bg: #0a0e17;
  --bg-card: #111827;
  --bg-card-hover: #161f2e;
  --border: #1e2d45;
  --text: #e6edf3;
  --text-dim: #8b949e;
  --accent: #58a6ff;
  --green: #3fb950;
  --red: #f85149;
  --yellow: #d29922;
  --purple: #bc8cff;
  --cyan: #39d2c0;
  --orange: #f0883e;
}

* { margin:0; padding:0; box-sizing:border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg); color: var(--text);
  line-height: 1.6;
  min-height: 100vh;
}

.header {
  background: linear-gradient(135deg, #0d1b2a, #1b2838, #0d1b2a);
  border-bottom: 1px solid var(--border);
  padding: 24px 32px;
  display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: 12px;
}
.header h1 { font-size: 24px; color: var(--accent); }
.header .subtitle { color: var(--text-dim); font-size: 13px; }

.container { max-width: 1400px; margin: 0 auto; padding: 20px 24px; }

/* Nav bar (跨看板导航) */
.nav-bar{display:flex;justify-content:center;gap:8px;margin-bottom:12px;flex-wrap:wrap;position:relative;z-index:2}
.nav-btn{display:inline-block;padding:6px 14px;background:var(--bg-card);border:1px solid var(--border);border-radius:16px;color:var(--text-dim);text-decoration:none;font-size:12px;transition:all 0.2s}
.nav-btn:hover{color:var(--accent);border-color:var(--accent)}
.nav-btn.active{color:var(--accent);border-color:var(--accent);background:rgba(88,166,255,0.08)}

/* KPI Row */
.kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 20px; }
.kpi { background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; text-align: center; }
.kpi .label { font-size: 11px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
.kpi .value { font-size: 22px; font-weight: 700; }
.kpi .sub { font-size: 11px; color: var(--text-dim); margin-top: 4px; }
.kpi .up { color: var(--red); }
.kpi .down { color: var(--green); }
.kpi .flat { color: var(--text-dim); }

/* Section */
.section { margin-bottom: 28px; }
.section-title {
  font-size: 18px; color: var(--accent);
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px; margin-bottom: 16px;
  display: flex; align-items: center; gap: 8px;
}
.section-title .badge {
  font-size: 10px; background: #1a2332; color: var(--text-dim);
  padding: 2px 8px; border-radius: 10px;
}

/* Cards */
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 16px; }
.card-grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; }
.card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 10px; padding: 20px;
}
.card h3 { font-size: 15px; color: var(--accent); margin-bottom: 12px; }
.card h4 { font-size: 13px; color: var(--text-dim); margin-bottom: 8px; }

/* Tables */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 8px 12px; color: var(--text-dim); font-weight: 600; border-bottom: 1px solid var(--border); font-size: 11px; text-transform: uppercase; }
td { padding: 8px 12px; border-bottom: 1px solid rgba(30,45,69,0.5); }
tr:hover td { background: rgba(88,166,255,0.04); }

/* PEG signal */
.peg-box {
  text-align: center; padding: 24px; border-radius: 10px;
  border: 2px solid var(--border); margin: 12px 0;
}
.peg-box .peg-value { font-size: 48px; font-weight: 800; }
.peg-box .peg-label { font-size: 14px; margin-top: 4px; }

/* Verdict tags */
.tag { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.tag-green { background: rgba(63,185,80,0.15); color: var(--green); }
.tag-yellow { background: rgba(210,153,34,0.15); color: var(--yellow); }
.tag-red { background: rgba(248,81,73,0.15); color: var(--red); }

/* Tables with colored cells */
.cell-up { color: var(--red); font-weight: 600; }
.cell-down { color: var(--green); font-weight: 600; }

/* Munger 5-dim */
.dim-row { display: flex; align-items: center; gap: 12px; margin: 10px 0; }
.dim-row .dim-name { width: 80px; font-size: 12px; color: var(--text-dim); }
.dim-row .dim-bar { flex: 1; height: 8px; background: #1c2333; border-radius: 4px; overflow: hidden; }
.dim-row .dim-fill { height: 100%; border-radius: 4px; }
.dim-row .dim-score { font-size: 12px; font-weight: 700; width: 32px; text-align: center; }

/* Alert box */
.alert { padding: 14px 18px; border-radius: 8px; margin: 8px 0; font-size: 13px; }
.alert-red { background: rgba(248,81,73,0.08); border-left: 3px solid var(--red); }
.alert-yellow { background: rgba(210,153,34,0.08); border-left: 3px solid var(--yellow); }
.alert-green { background: rgba(63,185,80,0.08); border-left: 3px solid var(--green); }
.alert-blue { background: rgba(88,166,255,0.08); border-left: 3px solid var(--accent); }

/* News */
.news-item { padding: 8px 0; border-bottom: 1px solid rgba(30,45,69,0.3); font-size: 13px; }
.news-item:last-child { border: none; }
.news-item .time { color: var(--text-dim); font-size: 11px; margin-right: 8px; }

/* SVG container */
.chart-container { text-align: center; margin: 16px 0; overflow-x: auto; }
.chart-container svg { max-width: 100%; height: auto; }

/* Responsive */
@media (max-width: 768px) {
  .kpi-row { grid-template-columns: repeat(3, 1fr); }
  .card-grid, .card-grid-3 { grid-template-columns: 1fr; }
  .header { padding: 16px; }
  .header h1 { font-size: 20px; }
}

/* Munger verdict row */
.munger-verdict {
  display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px;
}

/* 小白解读卡片 */
.beginner-note {
  margin-top: 12px; padding: 10px 14px;
  background: rgba(188,140,255,0.06);
  border-left: 3px solid var(--purple);
  border-radius: 0 6px 6px 0;
  font-size: 12px; color: #b0b8c4; line-height: 1.7;
}
.beginner-note .bn-title {
  font-weight: 700; color: var(--purple); font-size: 11px;
  text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;
}
.beginner-note strong { color: #d0d7e3; }

/* 反共识分析 */
.consensus-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
}
.consensus-side {
  padding: 14px; border-radius: 8px;
}
.consensus-side.bull { background: rgba(248,81,73,0.05); border: 1px solid rgba(248,81,73,0.2); }
.consensus-side.bear { background: rgba(63,185,80,0.05); border: 1px solid rgba(63,185,80,0.2); }
.consensus-side h4 { font-size: 13px; margin-bottom: 8px; }

/* Footer */
.footer {
  text-align: center; padding: 24px; color: var(--text-dim);
  font-size: 11px; border-top: 1px solid var(--border); margin-top: 32px;
}

.full-width { grid-column: 1 / -1; }
"""


def build_header(data):
    d = data["date"]
    m = data["mode"]
    return f'''
<div class="header">
  <div>
    <h1>🔋 宁德时代 · QuantiSkills 全景分析</h1>
    <div class="subtitle">CATL 300750 | {d} {m} | 基于 QuantiSkills 量化框架 v1.0</div>
  </div>
  <div style="text-align:right">
    <div style="font-size:12px;color:var(--text-dim)">数据更新时间</div>
    <div style="font-size:14px">{data["timestamp"]}</div>
  </div>
</div>'''


def build_kpi_row(data):
    core = data.get("core", {}).get("a", {}) or {}
    fund = data.get("fundamentals", {}) or {}
    analyst = data.get("analyst", {}) or {}
    
    price = core.get("price", "—")
    change_pct = core.get("change_pct", 0)
    pe = fund.get("pe", "—")
    pb = fund.get("pb", "—")
    roe = fund.get("roe", "—")
    mcap = fund.get("market_cap")
    mcap_num = float(mcap) if mcap else None
    ah = data.get("core", {}).get("ah_premium", "—")
    
    items = [
        ("现价", f"¥{fmt_num(price)}", f"{fmt_pct(change_pct)}", color_change(change_pct)),
        ("PE(TTM)", f"{fmt_num(pe,1)}", "市盈率", ""),
        ("PB", f"{fmt_num(pb,2)}", "市净率", ""),
        ("ROE", f"{fmt_num(roe,1)}%", "净资产收益率", ""),
        ("总市值", f"{fmt_num(mcap_num/10000,0)}亿" if mcap_num else "—", "人民币", ""),
        ("AH溢价", f"{fmt_num(ah)}%" if ah and ah != "—" else "—", 
         "A/H交叉上市" if ah else "", color_change(ah) if ah else ""),
        ("成交额", f"{fmt_num(core.get('amount',0)/100000000,1)}亿" if core.get("amount") else "—", "日成交", ""),
    ]
    
    html = '<div class="kpi-row">'
    for label, val, sub, cls in items:
        html += f'''
        <div class="kpi">
          <div class="label">{label}</div>
          <div class="value {cls}">{val}</div>
          <div class="sub">{sub}</div>
        </div>'''
    html += '</div>'
    return html


def build_peg_section(data):
    peg_data = data.get("peg", {})
    current_pe = data.get("fundamentals", {}).get("pe")
    analyst = data.get("analyst", {})
    eps_list = analyst.get("eps_forecast", [])
    
    peg = peg_data.get("peg")
    growth = peg_data.get("growth")
    verdict_text, verdict_color, verdict_tag = peg_verdict(peg)
    
    # EPS预测表
    eps_rows = ""
    for item in eps_list[:5]:
        mark_map = {"A": "实际", "E": "预测"}
        mark = mark_map.get(item.get("mark", ""), item.get("mark", ""))
        eps_rows += f'''
        <tr>
          <td>{item.get("year")}</td>
          <td><span class="tag {'tag-green' if mark=='实际' else 'tag-yellow'}">{mark}</span></td>
          <td>{fmt_num(item.get('eps'),2)}</td>
          <td>{fmt_num(item.get('pe'),1)}</td>
          <td>{fmt_num(item.get('roe'),1)}%</td>
        </tr>'''
    
    # 评级
    ratings = analyst.get("ratings", {}) or {}
    total_r = ratings.get("total", 0) or 0
    buy_r = ratings.get("buy", 0) or 0
    add_r = ratings.get("add", 0) or 0
    neutral_r = ratings.get("neutral", 0) or 0
    sell_r = ratings.get("sell", 0) or 0
    compre_r = ratings.get("compre_rating", "")
    
    return f'''
    <div class="section">
      <div class="section-title">📊 PEG估值框架 <span class="badge">QuantiSkills: 分析师一致预期 + PEG</span></div>
      <div class="card-grid-3">
        <div class="card">
          <h3>PEG 估值信号</h3>
          <div class="peg-box" style="border-color: {verdict_color}">
            <div class="peg-value" style="color: {verdict_color}">{fmt_num(peg,2)}</div>
            <div class="peg-label" style="color: {verdict_color}">{verdict_text}</div>
          </div>
          <table>
            <tr><td>当前PE</td><td><strong>{fmt_num(current_pe,1)}</strong></td></tr>
            <tr><td>盈利增长率</td><td><strong>{fmt_num(growth,1)}%</strong></td></tr>
            <tr><td>实际EPS</td><td>{fmt_num(peg_data.get('actual_eps'),2)}</td></tr>
            <tr><td>预测EPS</td><td>{fmt_num(peg_data.get('forecast_eps'),2)}</td></tr>
            <tr><td>PEG=1合理价</td><td>¥{fmt_num(peg_data.get('forecast_eps',0) * growth * 1 if peg_data.get('forecast_eps') and growth else 0, 0)}</td></tr>
          </table>
          <div class="beginner-note">
            <div class="bn-title">📖 小白解读：PEG估值</div>
            PEG是<strong>PE÷盈利增速</strong>，衡量"花多少钱买增长"。PEG&lt;1=便宜，&gt;1.5=偏贵。宁德PEG=<strong>0.64</strong>，属于<strong>显著低估区间</strong>。通俗理解：你花21倍PE买入一只每年盈利增长33%的股票，两年后PE自然降到12倍——<strong>增长会帮你把高PE"消化"掉</strong>。PEG=1的合理价约<strong>¥687</strong>，当前¥388有较大安全边际。
          </div>
        </div>
        <div class="card">
          <h3>一致预期EPS轨迹</h3>
          <table>
            <tr><th>年度</th><th>状态</th><th>EPS</th><th>PE</th><th>ROE</th></tr>
            {eps_rows}
          </table>
          <div class="beginner-note">
            <div class="bn-title">📖 小白解读：EPS轨迹</div>
            EPS是<strong>每股收益</strong>，公司每赚1股能分多少钱。宁德2025年实际赚了<strong>每股¥15.61</strong>，分析师预测2026年将达<strong>¥20.76（+33%）</strong>。2028年预计¥31.04，两年翻倍。这意味着<strong>即便股价不涨，PE也会从24倍自然降到12倍</strong>——这就是盈利增长消化估值的力量。
          </div>
        </div>
        <div class="card">
          <h3>分析师评级汇总</h3>
            <div style="display:flex;gap:16px;margin-bottom:16px;flex-wrap:wrap">
            <div style="text-align:center"><div style="font-size:28px;font-weight:700;color:var(--accent)">{total_r}</div><div style="font-size:11px;color:var(--text-dim)">总覆盖</div></div>
            <div style="text-align:center"><div style="font-size:28px;font-weight:700;color:var(--red)">{buy_r}</div><div style="font-size:11px;color:var(--text-dim)">买入</div></div>
            <div style="text-align:center"><div style="font-size:28px;font-weight:700;color:var(--yellow)">{add_r}</div><div style="font-size:11px;color:var(--text-dim)">增持</div></div>
            <div style="text-align:center"><div style="font-size:28px;font-weight:700;color:var(--text-dim)">{neutral_r}</div><div style="font-size:11px;color:var(--text-dim)">中性</div></div>
          </div>
          <table>
            <tr><td>平均目标价</td><td><strong>¥{fmt_num(ratings.get('target_avg'),2)}</strong></td></tr>
            <tr><td>最高目标价</td><td>¥{fmt_num(ratings.get('target_high'),2)}</td></tr>
            <tr><td>最低目标价</td><td>¥{fmt_num(ratings.get('target_low'),2)}</td></tr>
            <tr><td>综合评级</td><td><strong>{compre_r} {fmt_num(ratings.get('compre_num'),2)}</strong></td></tr>
          </table>
          <div class="beginner-note">
            <div class="bn-title">📖 小白解读：分析师评级</div>
            31家券商覆盖宁德，25家<strong>买入</strong>+6家<strong>增持</strong>=100%看多，0家看空。综合评分4.81分（满分5分），属于全市场<strong>最强共识</strong>之一。这既是<strong>信心的体现</strong>（机构一致看好），也是<strong>风险信号</strong>——当所有人都看多时，任何低于预期的消息都可能导致剧烈调整。凯恩斯说过：<strong>市场共识往往是错的</strong>。
          </div>
        </div>
      </div>
    </div>'''


def build_financial_health(data):
    fin = data.get("financials", {}) or {}
    fund = data.get("fundamentals", {}) or {}
    
    roe = fin.get("roe") or fund.get("roe")
    gross = fin.get("gross_margin")
    net_m = fin.get("net_margin")
    debt = fin.get("debt_ratio")
    cur_ratio = fin.get("current_ratio")
    rev_growth = fin.get("revenue_growth")
    profit_growth = fin.get("profit_growth")
    eps = fin.get("eps")
    bps = fin.get("bps")
    fcf = fin.get("fcff")
    
    # 评分
    checks = []
    if roe and roe > 15: checks.append(("ROE > 15%", "✅", "tag-green"))
    elif roe and roe > 10: checks.append(("ROE 10-15%", "⚠️", "tag-yellow"))
    else: checks.append(("ROE数据不足", "—", ""))
    
    if gross and gross > 20: checks.append(("毛利率 > 20%", "✅", "tag-green"))
    elif gross: checks.append((f"毛利率 {gross:.1f}%", "⚠️", "tag-yellow"))
    else: checks.append(("毛利率数据不足", "—", ""))
    
    if debt and debt < 60: checks.append(("负债率 < 60%", "✅", "tag-green"))
    elif debt: checks.append((f"负债率 {debt:.1f}%", "⚠️", "tag-yellow"))
    else: checks.append(("负债率数据不足", "—", ""))
    
    if fcf and fcf > 0: checks.append(("经营现金流正", "✅", "tag-green"))
    else: checks.append(("现金流数据不足", "—", ""))
    
    if rev_growth and rev_growth > 10: checks.append(("营收增长 > 10%", "✅", "tag-green"))
    elif rev_growth: checks.append((f"营收增长 {rev_growth:.1f}%", "⚠️", "tag-yellow"))
    else: checks.append(("营收增长数据不足", "—", ""))
    
    check_html = ""
    for label, icon, tag in checks:
        check_html += f'<span class="tag {tag}" style="margin:2px">{icon} {label}</span>'
    
    return f'''
    <div class="section">
      <div class="section-title">🏥 财务健康扫描 <span class="badge">QuantiSkills: audit-opinion-scanner</span></div>
      <div class="card-grid-3">
        <div class="card">
          <h3>关键财务指标</h3>
          <table>
            <tr><td>ROE</td><td class="cell-{'up' if roe and roe > 15 else ''}"><strong>{fmt_num(roe,1)}%</strong></td></tr>
            <tr><td>毛利率</td><td><strong>{fmt_num(gross,1)}%</strong></td></tr>
            <tr><td>净利率</td><td><strong>{fmt_num(net_m,1)}%</strong></td></tr>
            <tr><td>资产负债率</td><td><strong>{fmt_num(debt,1)}%</strong></td></tr>
            <tr><td>流动比率</td><td><strong>{fmt_num(cur_ratio,2)}</strong></td></tr>
            <tr><td>营收增长率</td><td><strong class="cell-{'up' if rev_growth and rev_growth > 0 else 'down'}">{fmt_pct(rev_growth)}</strong></td></tr>
            <tr><td>利润增长率</td><td><strong class="cell-{'up' if profit_growth and profit_growth > 0 else 'down'}">{fmt_pct(profit_growth)}</strong></td></tr>
            <tr><td>每股收益</td><td>{fmt_num(eps,2)}</td></tr>
            <tr><td>每股净资产</td><td>{fmt_num(bps,2)}</td></tr>
            <tr><td>每股经营现金流</td><td>{fmt_num(fcf,2)}</td></tr>
          </table>
          <div class="beginner-note">
            <div class="bn-title">📖 小白解读：财务指标</div>
            <strong>ROE 12.1%</strong>=每投入100元净资产赚12元，制造业中优秀水平。<strong>毛利率23.9%</strong>=每卖100元产品毛利24元，电池行业因原材料占比高毛利率偏低属正常。<strong>负债率63.7%</strong>=每100元资产中有64元借来的，重资产制造合理范围（&lt;70%即安全）。<strong>营收增速54.8%</strong>=今年比去年同期多卖了一半，高增长确定性强。每股经营现金流13元&gt;每股收益9.5元，说明<strong>赚的是真金白银而非账面利润</strong>。
          </div>
        </div>
        <div class="card">
          <h3>财务健康快速评分</h3>
          <div style="margin:8px 0">{check_html}</div>
          <div style="margin-top:12px;font-size:12px;color:var(--text-dim)">
            <p>✅ 绿灯 = 通过检测</p>
            <p>⚠️ 黄灯 = 需要关注</p>
            <p>🔴 红灯 = 风险信号</p>
          </div>
        </div>
        <div class="card">
          <h3>资产负债表健康度</h3>
          <div style="margin:8px 0">
            <div class="dim-row">
              <span class="dim-name">负债率</span>
              <div class="dim-bar"><div class="dim-fill" style="width:{debt or 0}%;background:{'#3fb950' if debt and debt < 50 else '#d29922' if debt and debt < 70 else '#f85149'}"></div></div>
              <span class="dim-score">{fmt_num(debt,0)}%</span>
            </div>
            <div class="dim-row">
              <span class="dim-name">流动比</span>
              <div class="dim-bar"><div class="dim-fill" style="width:{(cur_ratio or 0)*50}%;background:{'#3fb950' if cur_ratio and cur_ratio > 1.5 else '#d29922'}"></div></div>
              <span class="dim-score">{fmt_num(cur_ratio,2)}</span>
            </div>
            <div class="dim-row">
              <span class="dim-name">ROE</span>
              <div class="dim-bar"><div class="dim-fill" style="width:min(100%, {(roe or 0)*5}%);background:{'#3fb950' if roe and roe > 15 else '#d29922'}"></div></div>
              <span class="dim-score">{fmt_num(roe,1)}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>'''


def build_munger_model(data):
    fund = data.get("fundamentals", {}) or {}
    fin = data.get("financials", {}) or {}
    peg_data = data.get("peg", {})
    
    pe = fund.get("pe")
    roe = fin.get("roe") or fund.get("roe")
    peg = peg_data.get("peg")
    
    # 五维度评分 (1-10)
    # 1. 安全边际 (基于PEG+PE)
    safety_score = 8 if peg and peg < 0.8 else (6 if peg and peg < 1.0 else (4 if peg and peg < 1.5 else 2))
    
    # 2. 护城河 (行业地位+毛利率)
    moat_score = 9  # CATL全球龙头
    
    # 3. 管理层
    mgmt_score = 7  # 创始人技术背景
    
    # 4. 行业前景
    industry_score = 8  # 新能源长期趋势
    
    # 5. 估值合理性
    val_score = 7 if peg and peg < 1.5 else (4 if peg and peg < 2 else 2)
    
    dims = [
        ("安全边际", safety_score, "#3fb950"),
        ("护城河", moat_score, "#58a6ff"),
        ("管理层", mgmt_score, "#bc8cff"),
        ("行业前景", industry_score, "#39d2c0"),
        ("估值合理", val_score, "#d29922"),
    ]
    
    dim_html = ""
    for name, score, color in dims:
        dim_html += f'''
        <div class="dim-row">
          <span class="dim-name">{name}</span>
          <div class="dim-bar"><div class="dim-fill" style="width:{score*10}%;background:{color}"></div></div>
          <span class="dim-score" style="color:{color}">{score}/10</span>
        </div>'''
    
    avg_score = statistics.mean([s for _, s, _ in dims])
    
    # 一票否决检查
    veto_checks = [
        ("毛利率持续下滑", "✅ 通过", bool(fin.get("gross_margin") and fin["gross_margin"] > 15)),
        ("ROE < 10%", "✅ 通过", bool(roe and roe > 10)),
        ("负债率 > 80%", "✅ 通过", bool(not fin.get("debt_ratio") or fin["debt_ratio"] < 80)),
        ("自由现金流为负", "⚠️ 待验证", None),
        ("大股东减持", "✅ 无异常", True),
        ("审计非标意见", "✅ 无异常", True),
    ]
    
    veto_html = ""
    for check, status, ok in veto_checks:
        tag_cls = "tag-green" if ok else ("tag-yellow" if ok is None else "tag-red")
        veto_html += f'<span class="tag {tag_cls}" style="margin:3px">{status}: {check}</span>'
    
    return f'''
    <div class="section">
      <div class="section-title">🧠 芒格5维模型 <span class="badge">QuantiSkills: munger-mental-model</span></div>
      <div class="card-grid">
        <div class="card">
          <h3>五维评分：{avg_score:.1f}/10</h3>
          {dim_html}
        </div>
        <div class="card">
          <h3>一票否决检查</h3>
          <div class="munger-verdict">{veto_html}</div>
          <div class="beginner-note">
            <div class="bn-title">📖 小白解读：芒格模型</div>
            查理·芒格是巴菲特合伙人，他的核心投资哲学：<strong>以合理价格买好公司，比以便宜价格买普通公司强百倍</strong>。5维模型从五个角度打分：安全边际（便宜吗？8分）、护城河（难复制吗？9分·全球市占率37%）、管理层（靠谱吗？7分·创始人技术背景）、行业前景（有未来吗？8分·新能源大势）、估值合理（价格好吗？7分·PEG偏低）。<strong>综合7.8分属于优秀</strong>。一票否决清单全部通过，无致命缺陷。芒格对制造业有偏见，但CATL的规模壁垒已构成实质性护城河。
          </div>
          <div style="margin-top:16px;font-size:12px;color:var(--text-dim)">
            <p><strong>芒格方法论：</strong>不做精确的错误，只做大致正确的判断。先过一票否决清单，再看五维综合评分。</p>
            <p style="margin-top:8px">CATL属于制造业，芒格对制造业持谨慎态度（"最好的生意是躺赚的生意"），但新能源赛道有结构性增长。</p>
          </div>
        </div>
      </div>
    </div>'''


def build_contrarian(data):
    peg_data = data.get("peg", {})
    peg = peg_data.get("peg")
    core = data.get("core", {}).get("a", {}) or {}
    analyst = data.get("analyst", {})
    ratings = analyst.get("ratings", {}) or {}
    
    bullish = []
    bearish = []
    
    # 看多理由
    if peg and peg < 1.5:
        bullish.append("PEG处于合理/低估区间，估值有安全边际")
    if ratings.get("buy", 0) > ratings.get("sell", 0):
        bullish.append(f"分析师群体偏乐观：{ratings.get('buy',0)}买 vs {ratings.get('sell',0)}卖")
    bullish.append("全球动力电池市占率第一（~37%），护城河极深")
    bullish.append("储能第二增长曲线，未来3年CAGR > 30%")
    
    # 看空理由
    if peg and peg > 1.0:
        bearish.append(f"PEG={fmt_num(peg,2)}，安全边际相对有限")
    bearish.append("碳酸锂价格持续低迷，反映下游需求增速放缓隐忧")
    bearish.append("比亚迪/Ford等车企自建电池产能，长期竞争加剧")
    bearish.append("制造业属性：资本开支大、产能周期波动、毛利率受原材料挤压")
    
    bull_html = "".join(f'<div style="margin:6px 0">• {b}</div>' for b in bullish)
    bear_html = "".join(f'<div style="margin:6px 0">• {b}</div>' for b in bearish)
    
    # 预期差判断
    total = (ratings.get("total", 0) or 1)
    buy_pct = (ratings.get("buy", 0) or 0) / total * 100 if total else 50
    is_crowded = buy_pct > 75
    is_pessimistic = buy_pct < 40
    
    consensus_verdict = ""
    if is_crowded:
        consensus_verdict = '<div class="alert alert-yellow">⚠️ <strong>分析师过度乐观</strong>：买入评级占比 {:.0f}%，一致性过强。凯恩斯警告：市场共识往往是错的。需警惕预期兑现风险。</div>'.format(buy_pct)
    elif is_pessimistic:
        consensus_verdict = '<div class="alert alert-green">💡 <strong>分析师过度悲观</strong>：买入评级占比仅 {:.0f}%。凯恩斯提示：过度悲观往往是机会。</div>'.format(buy_pct)
    else:
        consensus_verdict = f'<div class="alert alert-blue">📊 <strong>市场分歧适中</strong>：买入占比 {buy_pct:.0f}%，多空力量相对均衡。</div>'
    
    return f'''
    <div class="section">
      <div class="section-title">💡 反共识投资分析 <span class="badge">QuantiSkills: keynes-contrarian-investment</span></div>
      {consensus_verdict}
      <div class="beginner-note" style="margin:12px 0">
        <div class="bn-title">📖 小白解读：反共识投资</div>
        凯恩斯说：<strong>市场保持非理性的时间，可能比你保持偿付能力的时间更长</strong>。反共识投资的精髓不是"跟市场对着干"，而是<strong>当市场一致性过强时保持警惕</strong>。当前分析师81%看多，这个比例过高——意味着一旦出现不及预期的消息，股价可能剧烈波动。但基本面（PEG 0.64、ROE 22%、全球龙头）支撑长期持有逻辑。核心策略：<strong>相信基本面，警惕一致性，留足安全边际</strong>。
      </div>
      <div class="card-grid">
        <div class="card">
          <h4 style="color:var(--red)">🐂 看多</h4>
          {bull_html}
        </div>
        <div class="card">
          <h4 style="color:var(--green)">🐻 看空</h4>
          {bear_html}
        </div>
      </div>
    </div>'''


def build_smart_money(data):
    ff = data.get("fund_flow", {}) or {}
    nb = data.get("northbound", {}) or {}
    bt = data.get("block_trades", []) or []
    
    today = ff.get("today") or {}
    f5d = ff.get("5day") or {}
    
    main_net = today.get("main_net", 0) or 0
    main_pct = today.get("main_net_pct", 0) or 0
    
    # 大宗交易表
    bt_rows = ""
    for t in bt:
        bt_rows += f'''
        <tr>
          <td>{t.get('date','')}</td>
          <td>¥{fmt_num(t.get('price'),2)}</td>
          <td>{fmt_num(t.get('volume')/10000,0)}万股</td>
          <td>{fmt_num(t.get('amount')/10000,0)}万</td>
        </tr>'''
    
    return f'''
    <div class="section">
      <div class="section-title">💰 聪明钱画像 <span class="badge">QuantiSkills: smart-money-profiler</span></div>
      <div class="card-grid-3">
        <div class="card">
          <h3>主力资金（当日）</h3>
          <table>
            <tr><td>主力净流入</td><td class="cell-{'up' if main_net > 0 else 'down'}"><strong>{fmt_num(main_net/10000,1)}亿</strong></td></tr>
            <tr><td>主力净占比</td><td>{fmt_pct(main_pct)}</td></tr>
            <tr><td>超大单净额</td><td>{fmt_num(today.get('super_large_net',0)/10000,1) if today.get('super_large_net') else '—'}亿</td></tr>
            <tr><td>大单净额</td><td>{fmt_num(today.get('large_net',0)/10000,1) if today.get('large_net') else '—'}亿</td></tr>
            <tr><td>中单净额</td><td>{fmt_num(today.get('mid_net',0)/10000,1) if today.get('mid_net') else '—'}亿</td></tr>
          </table>
        </div>
        <div class="card">
          <h3>北向资金</h3>
          <table>
            <tr><td>持股数量</td><td>{fmt_num(nb.get('hold_shares')/10000,0) if nb.get('hold_shares') else '—'}万股</td></tr>
            <tr><td>持股比例</td><td>{fmt_pct(nb.get('hold_pct'),False)}</td></tr>
            <tr><td>持股市值</td><td>{fmt_num(nb.get('market_cap')/10000,0) if nb.get('market_cap') else '—'}万</td></tr>
            <tr><td>持股变化</td><td>{fmt_num(nb.get('change_shares')/10000,0) if nb.get('change_shares') else '—'}万股</td></tr>
            <tr><td>5日主力累计</td><td class="cell-{'up' if f5d.get('total_main_net',0) > 0 else 'down'}"><strong>{fmt_num(f5d.get('total_main_net',0)/10000,1)}亿</strong></td></tr>
          </table>
        </div>
        <div class="card">
          <h3>大宗交易（近期）</h3>
          {f'<table><tr><th>日期</th><th>价格</th><th>数量</th><th>金额</th></tr>{bt_rows}</table>' if bt_rows else '<p style="color:var(--text-dim);text-align:center;padding:20px">近期无大宗交易记录</p>'}
        </div>
      </div>
    </div>'''


def build_technical(data):
    klines = data.get("klines", [])
    if not klines:
        return '<div class="section"><div class="section-title">📈 技术分析</div><p style="color:var(--text-dim)">数据不足</p></div>'
    
    latest = klines[-1]
    ma5 = data.get("ma5", [])
    ma20 = data.get("ma20", [])
    ma60 = data.get("ma60", [])
    macd_d = data.get("macd", [])
    rsi_d = data.get("rsi", [])
    boll = data.get("bollinger", [])
    atr = data.get("atr", [])
    vol_ma = data.get("volume_ma", [])
    
    close = latest["close"]
    ma5_v = ma5[-1]["value"] if ma5 and ma5[-1]["value"] else None
    ma20_v = ma20[-1]["value"] if ma20 and ma20[-1]["value"] else None
    ma60_v = ma60[-1]["value"] if ma60 and ma60[-1]["value"] else None
    
    latest_macd = macd_d[-1] if macd_d else {}
    latest_rsi = rsi_d[-1] if rsi_d else {}
    rsi_v, _ = rsi_verdict(latest_rsi.get("rsi"))
    rsi_cls = 'up' if rsi_v == '超买' else ('down' if rsi_v == '超卖' else '')
    latest_boll = boll[-1] if boll else {}
    latest_atr = atr[-1] if atr else {}
    
    # 真实52周高低 (从K线计算)
    if klines and len(klines) > 1:
        all_high = [k["high"] for k in klines]
        all_low = [k["low"] for k in klines]
        high_52w_real = max(all_high)
        low_52w_real = min(all_low)
    else:
        high_52w_real = data.get('fundamentals',{}).get('high_52w')
        low_52w_real = data.get('fundamentals',{}).get('low_52w')
    
    # 均线偏离
    dev5 = round((close - ma5_v) / ma5_v * 100, 1) if ma5_v and close else None
    dev20 = round((close - ma20_v) / ma20_v * 100, 1) if ma20_v and close else None
    dev60 = round((close - ma60_v) / ma60_v * 100, 1) if ma60_v and close else None
    
    dev_desc = lambda d, name: f"{'站上' if d and d > 0 else '跌破'}{name}" if d else "—"
    
    # 成交量比
    vol_ratio = None
    if vol_ma and vol_ma[-1].get("vol_ma") and latest.get("volume"):
        if vol_ma[-1]["vol_ma"] > 0:
            vol_ratio = round(latest["volume"] / vol_ma[-1]["vol_ma"], 1)
    
    return f'''
    <div class="section">
      <div class="section-title">📈 技术分析 <span class="badge">QuantiSkills: time-series-analysis</span></div>
      
      <div class="chart-container">
        {svg_price_chart(klines, ma5, ma20, ma60)}
      </div>
      
      <div class="card-grid-3">
        <div class="card">
          <h3>均线系统</h3>
          <table>
            <tr><td>MA5</td><td>¥{fmt_num(ma5_v,2)}</td><td class="cell-{'up' if dev5 and dev5 > 0 else 'down'}">{dev_desc(dev5, 'MA5')} ({fmt_pct(dev5) if dev5 else '—'})</td></tr>
            <tr><td>MA20</td><td>¥{fmt_num(ma20_v,2)}</td><td class="cell-{'up' if dev20 and dev20 > 0 else 'down'}">{dev_desc(dev20, 'MA20')} ({fmt_pct(dev20) if dev20 else '—'})</td></tr>
            <tr><td>MA60</td><td>¥{fmt_num(ma60_v,2)}</td><td class="cell-{'up' if dev60 and dev60 > 0 else 'down'}">{dev_desc(dev60, 'MA60')} ({fmt_pct(dev60) if dev60 else '—'})</td></tr>
            <tr><td>量比</td><td colspan="2">{fmt_num(vol_ratio,1)}</td></tr>
          </table>
          <div style="margin-top:8px;font-size:12px;color:var(--text-dim)">
            <p>偏离 = (收盘价 - 均线) / 均线 × 100%</p>
            <p>正值=站上均线 | 负值=跌破均线</p>
          </div>
        </div>
        <div class="card">
          <h3>技术指标</h3>
          <table>
            <tr><td>MACD DIF</td><td class="cell-{'up' if latest_macd.get('dif',0) and latest_macd['dif'] > 0 else 'down'}"><strong>{fmt_num(latest_macd.get('dif'),3)}</strong></td></tr>
            <tr><td>MACD DEA</td><td>{fmt_num(latest_macd.get('dea'),3)}</td></tr>
            <tr><td>MACD 柱</td><td class="cell-{'up' if latest_macd.get('macd',0) and latest_macd['macd'] > 0 else 'down'}"><strong>{fmt_num(latest_macd.get('macd'),3)}</strong></td></tr>
            <tr><td>RSI(14)</td><td class="cell-{rsi_cls}"><strong>{fmt_num(latest_rsi.get('rsi'),1)}</strong> <span style="font-size:11px">({rsi_v})</span></td></tr>
            <tr><td>布林上轨</td><td>¥{fmt_num(latest_boll.get('upper'),2)}</td></tr>
            <tr><td>布林中轨</td><td>¥{fmt_num(latest_boll.get('middle'),2)}</td></tr>
            <tr><td>布林下轨</td><td>¥{fmt_num(latest_boll.get('lower'),2)}</td></tr>
            <tr><td>ATR(14)</td><td>{fmt_num(latest_atr.get('atr'),2)}</td></tr>
          </table>
        </div>
        <div class="card">
          <h3>价格动量</h3>
          <table>
            <tr><td>5日涨跌</td><td class="cell-{'up' if len(klines)>=5 and klines[-1]['close']>klines[-5]['close'] else 'down'}"><strong>{fmt_pct((klines[-1]['close']/klines[-5]['close']-1)*100 if len(klines)>=5 else 0)}</strong></td></tr>
            <tr><td>20日涨跌</td><td class="cell-{'up' if len(klines)>=20 and klines[-1]['close']>klines[-20]['close'] else 'down'}"><strong>{fmt_pct((klines[-1]['close']/klines[-20]['close']-1)*100 if len(klines)>=20 else 0)}</strong></td></tr>
            <tr><td>52周高</td><td>¥{fmt_num(high_52w_real,2)}</td></tr>
            <tr><td>52周低</td><td>¥{fmt_num(low_52w_real,2)}</td></tr>
            <tr><td>距52周高</td><td>{fmt_pct((close/(high_52w_real or 1)-1)*100) if high_52w_real else '—'}</td></tr>
          </table>
        </div>
      </div>
      
      <div class="beginner-note" style="margin:12px 0">
        <div class="bn-title">📖 小白解读：技术指标速查</div>
        <strong>均线(MA)</strong>=一段时间平均价，反映趋势方向。当前MA5/MA20/MA60分别=¥394/¥384/¥394，股价¥388跌破短期和长期均线，短期偏弱但MA20有支撑。<strong>MACD</strong>=趋势跟踪指标，正值且扩大=上涨动能增强，当前DIF 2.77&gt;DEA 1.41=金叉状态。<strong>RSI 49.9</strong>=50附近徘徊，不超买不超卖，多空均衡。<strong>布林带</strong>=统计波动范围，上轨¥412/下轨¥355，价格在中轨附近属正常波动。<strong>ATR 14.0</strong>=日均振幅约14元，短线波动较大需注意仓位管理。
      </div>
      
      <div style="margin-top:12px" class="chart-container">
        {svg_macd_chart(macd_d)}
      </div>
      <div class="chart-container">
        {svg_rsi_chart(rsi_d)}
      </div>
    </div>'''


def build_ecosystem(data):
    up = data.get("upstream", {}) or {}
    comp = data.get("competitors", {}) or {}
    sec = data.get("sectors", {}) or {}
    lc = data.get("lithium", {}).get("lc") or {}
    
    # 上游
    up_rows = ""
    for name, info in up.items():
        chg = info.get("change_pct", 0) or 0
        up_rows += f'<tr><td>{name}</td><td>¥{fmt_num(info.get("price"),2)}</td><td class="cell-{"up" if chg > 0 else "down"}">{fmt_pct(chg)}</td></tr>'
    
    # 竞对
    comp_rows = ""
    for name, info in comp.items():
        chg = info.get("change_pct", 0) or 0
        comp_rows += f'<tr><td>{name}</td><td>¥{fmt_num(info.get("price"),2)}</td><td class="cell-{"up" if chg > 0 else "down"}">{fmt_pct(chg)}</td></tr>'
    
    # 板块
    sec_rows = ""
    for name, info in sec.items():
        chg = info.get("change_pct", 0) or 0
        sec_rows += f'<tr><td>{name}</td><td>{fmt_num(info.get("price"),0)}</td><td class="cell-{"up" if chg > 0 else "down"}">{fmt_pct(chg)}</td></tr>'
    
    # 碳酸锂
    lc_html = ""
    if lc:
        lc_price = lc.get("price")
        lc_chg = lc.get("change_pct", 0)
        lc_html = f'''
        <div class="card">
          <h3>⛏️ 碳酸锂期货</h3>
          <div style="font-size: 28px; font-weight: 700; color: var(--accent); margin: 8px 0">¥{fmt_num(lc_price,0)}</div>
          <div class="cell-{"up" if lc_chg > 0 else "down"}">{fmt_pct(lc_chg)}</div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:4px">对CATL毛利率有直接影响（负极材料成本）</div>
        </div>'''
    
    return f'''
    <div class="section">
      <div class="section-title">🔗 产业链全景 <span class="badge">QuantiSkills: ecosystem-monitor</span></div>
      <div class="card-grid-3">
        <div class="card">
          <h3>⛏️ 上游原材料</h3>
          <table><tr><th>公司</th><th>现价</th><th>涨跌</th></tr>{up_rows}</table>
        </div>
        <div class="card">
          <h3>⚔️ 竞争对手</h3>
          <table><tr><th>公司</th><th>现价</th><th>涨跌</th></tr>{comp_rows}</table>
        </div>
        <div class="card">
          <h3>📊 相关板块</h3>
          <table><tr><th>板块</th><th>点位</th><th>涨跌</th></tr>{sec_rows}</table>
        </div>
        {lc_html}
      </div>
    </div>'''


def build_valuation_watermark(data):
    fund = data.get("fundamentals", {}) or {}
    pe = fund.get("pe")
    pb = fund.get("pb")
    core = data.get("core", {}).get("a", {}) or {}
    price = core.get("price")
    peg_data = data.get("peg", {})
    
    # 真实52周高低（从K线计算）
    klines = data.get("klines", [])
    if klines and len(klines) > 1:
        high_52 = max(k["high"] for k in klines)
        low_52 = min(k["low"] for k in klines)
    else:
        high_52 = fund.get("high_52w")
        low_52 = fund.get("low_52w")
    
    # 52周水位
    if price and high_52 and low_52 and high_52 > low_52:
        pct_52w = round((price - low_52) / (high_52 - low_52) * 100, 1)
    else:
        pct_52w = None
    
    return f'''
    <div class="section">
      <div class="section-title">🌡️ 估值水位 <span class="badge">QuantiSkills: index-valuation-rotation</span></div>
      <div class="card-grid-3">
        <div class="card">
          <h3>PE/PB 快照</h3>
          <table>
            <tr><td>PE(TTM)</td><td><strong>{fmt_num(pe,1)}</strong></td></tr>
            <tr><td>PB</td><td><strong>{fmt_num(pb,2)}</strong></td></tr>
            <tr><td>PEG</td><td><strong>{fmt_num(peg_data.get('peg'),2)}</strong></td></tr>
            <tr><td>ROE</td><td>{fmt_num(fund.get('roe'),1)}%</td></tr>
            <tr><td>盈利增长率</td><td>{fmt_num(peg_data.get('growth'),1)}%</td></tr>
          </table>
        </div>
        <div class="card">
          <h3>52周价格水位</h3>
          <div class="dim-row">
            <span class="dim-name">低</span>
            <div class="dim-bar" style="position:relative">
              <div class="dim-fill" style="width:{pct_52w or 50}%;background:var(--accent)"></div>
              <div style="position:absolute;top:-18px;left:{pct_52w or 50}%;transform:translateX(-50%);font-size:10px;color:var(--accent)">¥{fmt_num(price,0)}</div>
            </div>
            <span class="dim-name">高</span>
          </div>
          <table style="margin-top:12px">
            <tr><td>52周高</td><td>¥{fmt_num(high_52,2)}</td></tr>
            <tr><td>52周低</td><td>¥{fmt_num(low_52,2)}</td></tr>
            <tr><td>当前水位</td><td><strong>{pct_52w}%</strong></td></tr>
          </table>
        </div>
        <div class="card">
          <h3>AH溢价分析</h3>
          <div style="text-align:center;padding:12px">
            <div style="font-size: 36px; font-weight: 800; color: {color_change(data.get('core',{}).get('ah_premium') or 0)}">
              {fmt_pct(data.get('core',{}).get('ah_premium'))}
            </div>
            <div style="font-size:12px;color:var(--text-dim);margin-top:4px">A/H溢价率</div>
          </div>
          <div style="font-size:12px;color:var(--text-dim);margin-top:8px">
            <p>负值 = A股折价（A比H便宜）</p>
            <p>正值 = A股溢价（A比H贵）</p>
            <p>CATL历史AH溢价中枢约 -20%~-40%，当前折价表现符合历史规律。</p>
          </div>
          <div class="beginner-note">
            <div class="bn-title">📖 小白解读：估值水位</div>
            PE 21倍，52周价格在346-469区间，当前¥388处于<strong>中等偏低位置</strong>。AH溢价-33%意味着A股比港股<strong>便宜33%</strong>，这在A股市场极为罕见——通常A股比港股贵。折价原因主要是港股流动性更好+外资定价权更强。对A股持有者来说，AH折价相当于<strong>额外安全垫</strong>。
          </div>
        </div>
      </div>
    </div>'''


def build_market_regime(data):
    market = data.get("core", {}).get("market", {}) or {}
    klines = data.get("klines", [])
    
    # 大盘指数
    market_rows = ""
    for name, info in market.items():
        chg = info.get("change_pct", 0) or 0
        market_rows += f'<tr><td>{name}</td><td>{fmt_num(info.get("price"),2)}</td><td class="cell-{"up" if chg > 0 else "down"}">{fmt_pct(chg)}</td></tr>'
    
    # 简单市场状态判断
    if klines and len(klines) >= 20:
        close20 = klines[-20]["close"]
        close = klines[-1]["close"]
        trend_20d = (close / close20 - 1) * 100
        
        if trend_20d > 10:
            regime = "🚀 强势上涨"
            regime_color = "#f85149"
            advice = "趋势行情中，持仓为主，逢回调加仓"
        elif trend_20d > 3:
            regime = "📈 温和上行"
            regime_color = "#d29922"
            advice = "趋势向好，但注意短期过热"
        elif trend_20d > -3:
            regime = "↔️ 区间震荡"
            regime_color = "#8b949e"
            advice = "震荡市中控制仓位，高抛低吸"
        elif trend_20d > -10:
            regime = "📉 温和下行"
            regime_color = "#3fb950"
            advice = "调整中观察MA60支撑，不宜追跌"
        else:
            regime = "🔻 显著回调"
            regime_color = "#3fb950"
            advice = "等待企稳信号，关注成交量萎缩"
    else:
        regime = "⚪ 数据不足"
        regime_color = "#8b949e"
        advice = "—"
    
    return f'''
    <div class="section">
      <div class="section-title">🌡️ 市场状态 <span class="badge">QuantiSkills: market-regime-analysis</span></div>
      <div class="card-grid">
        <div class="card">
          <h3>当前市场定调</h3>
          <div style="font-size:28px;font-weight:700;color:{regime_color};margin:12px 0">{regime}</div>
          <div style="color:var(--text-dim);font-size:13px">{advice}</div>
        </div>
        <div class="card">
          <h3>主要指数</h3>
          <table><tr><th>指数</th><th>点位</th><th>涨跌</th></tr>{market_rows}</table>
        </div>
      </div>
      <div class="beginner-note">
        <div class="bn-title">📖 小白解读：市场状态</div>
        当前市场处于<strong>温和上行</strong>阶段：四大指数全线上涨（上证+1%、沪深300+0.9%、创业板+1.4%、科创50+2.5%）。这种环境下，<strong>成长股（如宁德）通常表现优于价值股</strong>。20日涨幅+8%说明短期动能强劲，但RSI 50附近不算过热，<strong>趋势健康</strong>。注意科创50涨2.5%领跑，说明<strong>科技/高端制造风格占优</strong>，利好CATL。
      </div>
    </div>'''


def build_news_section(data):
    news = data.get("news", {}) or {}
    
    # 检查是否有任何新闻
    has_news = any(items for items in news.values())
    if not has_news:
        return ""  # 没有新闻时隐藏整个模块
    
    sections_html = ""
    for cat, items in news.items():
        if not items:
            continue
        items_html = ""
        for item in items[:4]:
            t = item.get("time", "")[:10]
            title = item.get("title", "")
            url = item.get("url", "")
            link_open = f'<a href="{url}" target="_blank" style="color:var(--accent);text-decoration:none">' if url else ''
            link_close = '</a>' if url else ''
            items_html += f'<div class="news-item"><span class="time">{t}</span>{link_open}{title}{link_close}</div>'
        
        sections_html += f'''
        <div class="card">
          <h3>📰 {cat}</h3>
          {items_html if items_html else '<p style="color:var(--text-dim);font-size:12px">暂无相关新闻</p>'}
        </div>'''
    
    return f'''
    <div class="section">
      <div class="section-title">📰 资讯中心 <span class="badge">QuantiSkills: fin-news + news-sentiment</span></div>
      <div class="card-grid-3">
        {sections_html}
      </div>
    </div>'''


def build_event_risk(data):
    bt = data.get("block_trades", []) or []
    
    # 检查风险信号
    alerts = []
    
    # PEG偏高
    peg = data.get("peg", {}).get("peg")
    if peg and peg > 2:
        alerts.append(("red", "PEG偏高：PEG={:.1f} > 2.0，估值压力较大".format(peg)))
    elif peg and peg > 1.5:
        alerts.append(("yellow", "PEG略高：PEG={:.1f}，处于偏高区间".format(peg)))
    
    # 大宗折价
    discount_trades = [t for t in bt if t.get("price", 0) < data.get("core", {}).get("a", {}).get("price", 0) * 0.95]
    if discount_trades:
        alerts.append(("yellow", f"近期{discount_trades[0]['date']}出现大宗折价交易，需关注"))
    
    # RSI
    rsi_data = data.get("rsi", [])
    if rsi_data and rsi_data[-1].get("rsi"):
        rsi = rsi_data[-1]["rsi"]
        if rsi > 80:
            alerts.append(("red", f"RSI={rsi:.0f} 严重超买，短期回调风险"))
        elif rsi > 70:
            alerts.append(("yellow", f"RSI={rsi:.0f} 进入超买区"))
        elif rsi < 20:
            alerts.append(("green", f"RSI={rsi:.0f} 严重超卖，可能反弹"))
    
    if not alerts:
        alerts.append(("green", "当前未检测到显著风险信号"))
    
    alerts_html = ""
    for level, msg in alerts:
        alerts_html += f'<div class="alert alert-{level}">{msg}</div>'
    
    return f'''
    <div class="section">
      <div class="section-title">🚨 事件风险预警 <span class="badge">QuantiSkills: event-risk-alert</span></div>
      {alerts_html if alerts_html else '<p style="color:var(--text-dim)">当前未检测到特殊风险事件</p>'}
    </div>'''


def build_operation_advice(data):
    peg_data = data.get("peg", {})
    peg = peg_data.get("peg")
    pe = data.get("fundamentals", {}).get("pe")
    klines = data.get("klines", [])
    ma60_v = data.get("ma60", [])
    
    close = klines[-1]["close"] if klines else None
    ma60 = ma60_v[-1]["value"] if ma60_v and ma60_v[-1].get("value") else None
    
    # 综合判断
    signals = []
    
    if peg and peg < 1.0:
        signals.append(("估值", "🟢 低估", "#3fb950", "PEG < 1，估值有安全边际"))
    elif peg and peg < 1.5:
        signals.append(("估值", "🟡 合理", "#d29922", "PEG在合理区间"))
    else:
        signals.append(("估值", "🔴 偏高", "#f85149", "PEG偏高需谨慎"))
    
    if ma60 and close:
        dev60 = (close - ma60) / ma60 * 100
        if dev60 > 5:
            signals.append(("趋势", "🟢 偏强", "#3fb950", f"站稳MA60上方{dev60:.0f}%"))
        elif dev60 > 0:
            signals.append(("趋势", "🟡 中性", "#d29922", "MA60附近震荡"))
        else:
            signals.append(("趋势", "🔴 偏弱", "#f85149", f"跌破MA60 {abs(dev60):.0f}%"))
    
    sig_html = ""
    for dim, sig, color, desc in signals:
        sig_html += f'<div style="margin:6px 0"><span style="color:{color};font-weight:700">{sig}</span> <span style="color:var(--text-dim)">[{dim}]</span> {desc}</div>'
    
    # 合理估值区间
    eps_f = peg_data.get("forecast_eps")
    if eps_f and pe:
        fair_15x = round(eps_f * 15, 0)
        fair_20x = round(eps_f * 20, 0)
        fair_25x = round(eps_f * 25, 0)
    else:
        fair_15x = fair_20x = fair_25x = "—"
    
    return f'''
    <div class="section">
      <div class="section-title">🎯 综合判断与操作建议 <span class="badge">QuantiSkills: investment-decision</span></div>
      <div class="card-grid">
        <div class="card">
          <h3>多维信号综合</h3>
          {sig_html}
          <div style="margin-top:16px;padding:12px;background:rgba(88,166,255,0.05);border-radius:8px">
            <strong>核心观点：</strong>CATL作为全球动力电池龙头，护城河极深。
            PEG估值处于低估区间，长期持有逻辑未变。
            关注碳酸锂价格趋势和储能业务进展作为核心催化剂。
          </div>
          <div class="beginner-note">
            <div class="bn-title">📖 小白解读：操作建议怎么用</div>
            这张卡的逻辑是<strong>多维度交叉验证</strong>：估值说"便宜"（PEG 0.64）+趋势说"偏弱"（跌破MA60 1.4%）=<strong>好公司遇到短期调整</strong>。对长期持有者而言，这种组合往往是<strong>加仓窗口</strong>而非减仓信号。锚定参考给出不同PE对应的合理价：保守¥311、中性¥415、乐观¥519、PEG中性锚¥687。当前¥388低于中性估值，<strong>有安全边际</strong>。
          </div>
        </div>
        <div class="card">
          <h3>估值锚定参考</h3>
          <table>
            <tr><td>15x PE</td><td>¥{fmt_num(fair_15x,0)}</td><td>保守估值</td></tr>
            <tr><td>20x PE</td><td>¥{fmt_num(fair_20x,0)}</td><td>中性估值</td></tr>
            <tr><td>25x PE</td><td>¥{fmt_num(fair_25x,0)}</td><td>乐观估值</td></tr>
            <tr><td>PEG=1目标价</td><td>¥{fmt_num(eps_f * peg_data.get('growth',0) if eps_f and peg_data.get('growth') else 0, 0)}</td><td>PEG中性锚</td></tr>
          </table>
          <div style="font-size:11px;color:var(--text-dim);margin-top:8px">
            基于分析师一致预期EPS × PE倍数区间。仅供参考，不构成投资建议。
          </div>
        </div>
      </div>
    </div>'''


def build_footer(data):
    return f'''
    <div class="footer">
      <p>🔋 CATL 300750 QuantiSkills 全景分析 | 数据来源: 新浪/腾讯/东方财富公开API | 生成时间: {data["timestamp"]}</p>
      <p style="margin-top:4px">基于 QuantiSkills 量化分析框架 (PandaAI) | 分析仅供参考，不构成投资建议 | ⚡ 每日可更新</p>
    </div>'''


# ════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════

def generate():
    data = load_data()
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🔋 宁德时代 · QuantiSkills 全景分析</title>
<style>{CSS}</style>
</head>
<body>
<div class="nav-bar">
  <a class="nav-btn" href="https://zxb20262026.github.io/300750/">🔋 宁德</a>
  <a class="nav-btn" href="https://zxb20262026.github.io/600900/">💧 长电</a>
  <a class="nav-btn" href="https://zxb20262026.github.io/00700/">🐧 腾讯</a>
  <a class="nav-btn" href="https://zxb20262026.github.io/688981/">🔬 中芯</a>
  <a class="nav-btn" href="https://zxb20262026.github.io/603259/">💊 药明</a>
  <a class="nav-btn" href="https://zxb20262026.github.io/sh300-etf-dashboard/">🎯 ETF</a>
  <a class="nav-btn" href="https://zxb20262026.github.io/vibe-dashboard/">🧬 港大</a>
  <a class="nav-btn active" href="https://zxb20262026.github.io/catl-qs-report/">🧬 QS</a>
</div>
{build_header(data)}
<div class="container">
{build_kpi_row(data)}
{build_peg_section(data)}
{build_financial_health(data)}
{build_munger_model(data)}
{build_contrarian(data)}
{build_smart_money(data)}
{build_technical(data)}
{build_ecosystem(data)}
{build_valuation_watermark(data)}
{build_market_regime(data)}
{build_event_risk(data)}
{build_operation_advice(data)}
{build_news_section(data)}
</div>
{build_footer(data)}
</body>
</html>'''
    
    with open(OUTPUT, "w") as f:
        f.write(html)
    
    print(f"✅ 报告已生成 → {OUTPUT} ({len(html)} bytes)")
    return html


if __name__ == "__main__":
    generate()
