#!/usr/bin/env python3
import json

with open("/root/strategy_repo/extracted_data.json") as f:
    data = json.load(f)

hourly_eq = data["hourly_equity"]

# 采样或使用所有点
points = hourly_eq
N = len(points)

# 画布尺寸
W = 1000
H = 560
pad_l = 80
pad_r = 50
pad_t = 80
pad_b = 70

plot_w = W - pad_l - pad_r
plot_h = H - pad_t - pad_b

# 提取序列
totals = [p["total"] for p in points]
frees = [p["free"] for p in points]
lockeds = [p["locked"] for p in points]

min_val = min(min(totals), min(frees)) * 0.95
max_val = max(totals) * 1.05

def to_x(i):
    return pad_l + (i / max(1, N - 1)) * plot_w

def to_y(v):
    return pad_t + plot_h - ((v - min_val) / max(1e-4, max_val - min_val)) * plot_h

# 构造折线路径
def make_path(vals):
    pts = [f"{to_x(i):.1f},{to_y(v):.1f}" for i, v in enumerate(vals)]
    return "M " + " L ".join(pts)

# 构造面积路径
def make_area(vals):
    pts = [f"{to_x(i):.1f},{to_y(v):.1f}" for i, v in enumerate(vals)]
    y_base = to_y(min_val)
    return f"M {to_x(0):.1f},{y_base:.1f} L " + " L ".join(pts) + f" L {to_x(N-1):.1f},{y_base:.1f} Z"

path_total = make_path(totals)
area_total = make_area(totals)

path_free = make_path(frees)
area_free = make_area(frees)

# 关键统计数据
start_total = totals[0]
end_total = totals[-1]
pnl = end_total - start_total
pnl_pct = (pnl / start_total) * 100.0
peak_total = max(totals)
t_start = points[0]["time"]
t_end = points[-1]["time"]

# 网格线与 Y 轴刻度
y_ticks = 5
grid_lines = []
for i in range(y_ticks + 1):
    val = min_val + (max_val - min_val) * (i / y_ticks)
    y_pos = to_y(val)
    grid_lines.append(f'''
    <line x1="{pad_l}" y1="{y_pos:.1f}" x2="{W - pad_r}" y2="{y_pos:.1f}" stroke="#22272e" stroke-dasharray="4,4"/>
    <text x="{pad_l - 12}" y="{y_pos + 4:.1f}" fill="#768390" font-size="11" text-anchor="end" font-family="monospace">${val:,.0f}</text>
    ''')

# X 轴时间刻度
x_ticks = 5
x_labels = []
for i in range(x_ticks + 1):
    idx = int((N - 1) * (i / x_ticks))
    p = points[idx]
    x_pos = to_x(idx)
    # 取月-日 时
    t_short = p["time"][5:]
    x_labels.append(f'''
    <line x1="{x_pos:.1f}" y1="{pad_t}" x2="{x_pos:.1f}" y2="{H - pad_b}" stroke="#1e2228" stroke-dasharray="2,4"/>
    <text x="{x_pos:.1f}" y="{H - pad_b + 22}" fill="#768390" font-size="11" text-anchor="middle" font-family="monospace">{t_short}</text>
    ''')

# 最新点坐标
last_x = to_x(N - 1)
last_y_tot = to_y(end_total)
last_y_free = to_y(frees[-1])

svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="background:#0d1117;">
  <defs>
    <!-- 总权益渐变 -->
    <linearGradient id="gradTotal" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#3fb950" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="#3fb950" stop-opacity="0.0"/>
    </linearGradient>
    <!-- 余额渐变 -->
    <linearGradient id="gradFree" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#58a6ff" stop-opacity="0.20"/>
      <stop offset="100%" stop-color="#58a6ff" stop-opacity="0.0"/>
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>

  <!-- 边框背景装饰 -->
  <rect x="0" y="0" width="{W}" height="{H}" fill="#0d1117" rx="12"/>
  <rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" fill="#161b22" rx="6" stroke="#30363d" stroke-width="1"/>

  <!-- 标题与摘要面板 -->
  <text x="{pad_l}" y="38" fill="#f0f6fc" font-size="20" font-weight="700" font-family="system-ui, -apple-system, sans-serif">
    NautilusTrader 策略实盘账户权益走势 (OKX Demo)
  </text>
  <text x="{pad_l}" y="60" fill="#8b949e" font-size="12" font-family="system-ui, sans-serif">
    时段: {t_start} 至 {t_end} (UTC+8) | 标的: BTC, ETH, SOL, BNB
  </text>

  <!-- 右上角 KPI 卡片 -->
  <g transform="translate({W - pad_r - 280}, 20)">
    <rect width="280" height="48" fill="#21262d" rx="6" stroke="#30363d"/>
    <text x="14" y="20" fill="#8b949e" font-size="11" font-family="system-ui">最新总权益 / 净盈亏</text>
    <text x="14" y="38" fill="#3fb950" font-size="16" font-weight="700" font-family="monospace">${end_total:,.2f}</text>
    <text x="160" y="38" fill="{ '#3fb950' if pnl>=0 else '#f85149' }" font-size="14" font-weight="700" font-family="monospace">
      { '+' if pnl>=0 else '' }{pnl:,.2f} ({ '+' if pnl_pct>=0 else '' }{pnl_pct:.2f}%)
    </text>
  </g>

  <!-- 网格与轴线 -->
  {''.join(grid_lines)}
  {''.join(x_labels)}

  <!-- 填充面积 -->
  <path d="{area_total}" fill="url(#gradTotal)"/>
  <path d="{area_free}" fill="url(#gradFree)"/>

  <!-- 折线 -->
  <!-- 自由余额折线 (蓝色) -->
  <path d="{path_free}" fill="none" stroke="#58a6ff" stroke-width="2" stroke-linejoin="round"/>
  <!-- 总权益折线 (绿色高亮) -->
  <path d="{path_total}" fill="none" stroke="#3fb950" stroke-width="3" stroke-linejoin="round" filter="url(#glow)"/>

  <!-- 最新点圆点与标注 -->
  <circle cx="{last_x:.1f}" cy="{last_y_tot:.1f}" r="5" fill="#3fb950" stroke="#f0f6fc" stroke-width="2"/>
  <circle cx="{last_x:.1f}" cy="{last_y_free:.1f}" r="4" fill="#58a6ff" stroke="#f0f6fc" stroke-width="2"/>

  <!-- 图例 (底部) -->
  <g transform="translate({pad_l}, {H - 24})">
    <!-- 总权益 -->
    <line x1="0" y1="0" x2="20" y2="0" stroke="#3fb950" stroke-width="3"/>
    <circle cx="10" cy="0" r="3" fill="#3fb950"/>
    <text x="28" y="4" fill="#c9d1d9" font-size="12" font-family="system-ui">账户总权益 (Total Equity: 包含持仓浮动盈亏)</text>

    <!-- 自由余额 -->
    <line x1="330" y1="0" x2="350" y2="0" stroke="#58a6ff" stroke-width="2"/>
    <circle cx="340" cy="0" r="3" fill="#58a6ff"/>
    <text x="358" y="4" fill="#c9d1d9" font-size="12" font-family="system-ui">可用现金余额 (Free USDT Cash)</text>

    <!-- 持仓市值/保证金 -->
    <rect x="580" y="-7" width="14" height="14" fill="#3fb950" fill-opacity="0.25" stroke="#3fb950" stroke-width="1"/>
    <text x="602" y="4" fill="#c9d1d9" font-size="12" font-family="system-ui">持仓占用保证金与市值差额 (Position Margin)</text>
  </g>
</svg>'''

with open("/root/strategy_repo/equity_curve.svg", "w") as f:
    f.write(svg_content)

print("SVG 曲线图已成功生成: /root/strategy_repo/equity_curve.svg")
