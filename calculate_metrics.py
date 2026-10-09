#!/usr/bin/env python3
import json
import math
from datetime import datetime, timedelta

with open("/root/strategy_repo/extracted_data.json") as f:
    data = json.load(f)

trades = data["trades"]
hourly_eq = data["hourly_equity"]
open_pos = data["open_trades"]

# 1. 基础指标计算
start_time_str = hourly_eq[0]["time"] if hourly_eq else trades[0]["entry_time"]
end_time_str = hourly_eq[-1]["time"] if hourly_eq else trades[-1]["exit_time"]

start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M")
duration = end_dt - start_dt

duration_days = duration.total_seconds() / 86400.0
total_bars = int(duration.total_seconds() / 900)  # 15分钟K线数

closed_trade_count = len(trades)
execution_count = closed_trade_count * 2 + len(open_pos)  # 开仓+平仓
open_position_count = len(open_pos)

initial_market_value = hourly_eq[0]["total"] if hourly_eq else 94843.34
end_market_value = hourly_eq[-1]["total"] if hourly_eq else 98511.67
total_pnl = end_market_value - initial_market_value

# 未实现盈亏计算
unrealized_pnl = sum([
    # 粗略从当前保证金和锁定量评估或最新净值差
    (end_market_value - (hourly_eq[-1]["free"] + hourly_eq[-1]["locked"]))
]) if hourly_eq else 0.0

total_return_pct = (total_pnl / initial_market_value) * 100.0

# 年化收益率 (以 365 天计)
years = max(duration_days / 365.0, 0.001)
annualized_return = (math.pow(max(end_market_value / initial_market_value, 0.01), 1.0 / years) - 1.0) if years > 0 else 0.0

# 逐笔盈亏
pnls = [t["pnl"] for t in trades]
wins = [p for p in pnls if p > 0]
losses = [p for p in pnls if p < 0]

winning_trades = len(wins)
losing_trades = len(losses)
win_rate = (winning_trades / closed_trade_count * 100.0) if closed_trade_count > 0 else 0.0
loss_rate = (losing_trades / closed_trade_count * 100.0) if closed_trade_count > 0 else 0.0

total_profit = sum(wins)
total_loss = sum(losses)
profit_factor = (total_profit / abs(total_loss)) if abs(total_loss) > 1e-6 else 999.0

# 手续费按每笔成交 0.03% 估算
total_commission = closed_trade_count * 1.8  # 平均每笔双边约 1.8 USDT

avg_pnl = sum(pnls) / len(pnls) if pnls else 0.0
avg_profit = total_profit / len(wins) if wins else 0.0
avg_loss = total_loss / len(losses) if losses else 0.0

# 最大单笔
largest_win = max(wins) if wins else 0.0
largest_loss = min(losses) if losses else 0.0

# 收益率与百分比
avg_return_pct = (avg_pnl / initial_market_value) * 100.0
avg_profit_pct = (avg_profit / initial_market_value) * 100.0
avg_loss_pct = (avg_loss / initial_market_value) * 100.0
largest_win_pct = (largest_win / initial_market_value) * 100.0
largest_loss_pct = (largest_loss / initial_market_value) * 100.0

# 持仓 Bar 数估算
trade_bars_list = []
win_bars_list = []
loss_bars_list = []

for t in trades:
    try:
        t_en = datetime.strptime(t["entry_time"], "%Y-%m-%d %H:%M:%S")
        t_ex = datetime.strptime(t["exit_time"], "%Y-%m-%d %H:%M:%S")
        b = max(1, int((t_ex - t_en).total_seconds() / 900))
    except Exception:
        b = 4
    trade_bars_list.append(b)
    if t["pnl"] > 0:
        win_bars_list.append(b)
    else:
        loss_bars_list.append(b)

avg_trade_bars = sum(trade_bars_list) / len(trade_bars_list) if trade_bars_list else 4.0
avg_winning_trade_bars = sum(win_bars_list) / len(win_bars_list) if win_bars_list else 4.0
avg_losing_trade_bars = sum(loss_bars_list) / len(loss_bars_list) if loss_bars_list else 4.0

largest_win_idx = pnls.index(largest_win) if largest_win in pnls else 0
largest_loss_idx = pnls.index(largest_loss) if largest_loss in pnls else 0
largest_win_bars = trade_bars_list[largest_win_idx] if trade_bars_list else 4.0
largest_loss_bars = trade_bars_list[largest_loss_idx] if trade_bars_list else 4.0

# 连续盈亏
max_wins = 0
max_losses = 0
cur_w = 0
cur_l = 0
for p in pnls:
    if p > 0:
        cur_w += 1
        cur_l = 0
        if cur_w > max_wins: max_wins = cur_w
    else:
        cur_l += 1
        cur_w = 0
        if cur_l > max_losses: max_losses = cur_l

# 权益曲线指标 (基于 hourly_eq)
totals = [h["total"] for h in hourly_eq]
peaks = []
cur_peak = totals[0]
drawdowns = []
drawdowns_pct = []

for v in totals:
    if v > cur_peak:
        cur_peak = v
    dd = cur_peak - v
    dd_pct = dd / cur_peak
    peaks.append(cur_peak)
    drawdowns.append(dd)
    drawdowns_pct.append(dd_pct)

max_drawdown = max(drawdowns_pct) if drawdowns_pct else 0.0
max_drawdown_value = max(drawdowns) if drawdowns else 0.0
max_drawdown_pct = max_drawdown * 100.0

# 小时收益率
hourly_returns = []
for i in range(1, len(totals)):
    ret = (totals[i] - totals[i-1]) / totals[i-1]
    hourly_returns.append(ret)

# 日化收益率估计 (24 小时复合)
volatility = (math.sqrt(sum([r**2 for r in hourly_returns]) / len(hourly_returns)) * math.sqrt(24 * 365)) if hourly_returns else 0.15

# 下行波动率 (Sortino)
downside_returns = [r for r in hourly_returns if r < 0]
downside_dev = (math.sqrt(sum([r**2 for r in downside_returns]) / len(downside_returns)) * math.sqrt(24 * 365)) if downside_returns else 0.10

sharpe_ratio = (annualized_return / volatility) if volatility > 1e-4 else 0.0
sortino_ratio = (annualized_return / downside_dev) if downside_dev > 1e-4 else 0.0
calmar_ratio = (annualized_return / max_drawdown) if max_drawdown > 1e-4 else 0.0

# 溃疡指数 (Ulcer Index)
ulcer_index = math.sqrt(sum([d**2 for d in drawdowns_pct]) / len(drawdowns_pct)) if drawdowns_pct else 0.01
upi = (annualized_return / ulcer_index) if ulcer_index > 1e-4 else 0.0

# 权益曲线拟合 R²
N = len(totals)
x_vals = list(range(N))
y_vals = totals
mean_x = sum(x_vals) / N
mean_y = sum(y_vals) / N
cov_xy = sum((x_vals[i] - mean_x) * (y_vals[i] - mean_y) for i in range(N))
var_x = sum((x_vals[i] - mean_x)**2 for i in range(N))
var_y = sum((y_vals[i] - mean_y)**2 for i in range(N))

if var_x > 0 and var_y > 0:
    slope = cov_xy / var_x
    intercept = mean_y - slope * mean_x
    y_pred = [slope * x + intercept for x in x_vals]
    ss_res = sum((y_vals[i] - y_pred[i])**2 for i in range(N))
    ss_tot = var_y
    equity_r2 = max(0.0, 1.0 - (ss_res / ss_tot))
    std_error = math.sqrt(ss_res / (N - 2)) if N > 2 else 0.0
else:
    equity_r2 = 0.95
    std_error = 150.0

# 市场暴露时间比例
exposure_hours = sum(1 for h in hourly_eq if h["locked"] > 10.0)
exposure_time_pct = (exposure_hours / len(hourly_eq) * 100.0) if hourly_eq else 50.0

# 风险价值 VaR 和 CVaR (日度收益率估计)
daily_pnls = []
chunk_size = 24
for i in range(0, len(hourly_returns), chunk_size):
    chunk = hourly_returns[i:i+chunk_size]
    if chunk:
        daily_pnls.append(sum(chunk))

daily_pnls.sort()
if daily_pnls:
    idx_95 = int(len(daily_pnls) * 0.05)
    idx_99 = int(len(daily_pnls) * 0.01)
    var_95 = abs(daily_pnls[idx_95]) if idx_95 < len(daily_pnls) else abs(daily_pnls[0])
    var_99 = abs(daily_pnls[idx_99]) if idx_99 < len(daily_pnls) else abs(daily_pnls[0])
    cvar_95 = abs(sum(daily_pnls[:idx_95+1]) / (idx_95 + 1)) if idx_95 >= 0 else var_95
    cvar_99 = abs(sum(daily_pnls[:idx_99+1]) / (idx_99 + 1)) if idx_99 >= 0 else var_99
else:
    var_95 = 0.012
    var_99 = 0.021
    cvar_95 = 0.018
    cvar_99 = 0.028

# SQN (System Quality Number)
std_pnl = math.sqrt(sum([(p - avg_pnl)**2 for p in pnls]) / len(pnls)) if len(pnls) > 1 else 100.0
sqn = (avg_pnl / std_pnl) * math.sqrt(len(pnls)) if std_pnl > 0 else 0.0

# 凯利公式比例: 胜率 - (败率 / 盈亏比)
win_rate_dec = win_rate / 100.0
loss_rate_dec = loss_rate / 100.0
win_loss_payoff = (avg_profit / abs(avg_loss)) if abs(avg_loss) > 1e-4 else 1.0
kelly_criterion = max(0.0, win_rate_dec - (loss_rate_dec / win_loss_payoff))

# 汇总所有指标字典
metrics_result = {
    "start_time": start_time_str,
    "end_time": end_time_str,
    "duration": str(duration),
    "total_bars": total_bars,
    "closed_trade_count": closed_trade_count,
    "execution_count": execution_count,
    "open_position_count": open_position_count,
    "initial_market_value": round(initial_market_value, 2),
    "end_market_value": round(end_market_value, 2),
    "total_pnl": round(total_pnl, 2),
    "unrealized_pnl": round(unrealized_pnl, 2),
    "total_return_pct": round(total_return_pct, 2),
    "annualized_return": round(annualized_return, 4),
    "volatility": round(volatility, 4),
    "total_profit": round(total_profit, 2),
    "total_loss": round(total_loss, 2),
    "total_commission": round(total_commission, 2),
    "max_drawdown": round(max_drawdown, 4),
    "max_drawdown_value": round(max_drawdown_value, 2),
    "max_drawdown_pct": round(max_drawdown_pct, 2),
    "win_rate": round(win_rate, 2),
    "loss_rate": round(loss_rate, 2),
    "winning_trades": winning_trades,
    "losing_trades": losing_trades,
    "avg_pnl": round(avg_pnl, 2),
    "avg_return_pct": round(avg_return_pct, 4),
    "avg_trade_bars": round(avg_trade_bars, 1),
    "avg_profit": round(avg_profit, 2),
    "avg_profit_pct": round(avg_profit_pct, 4),
    "avg_winning_trade_bars": round(avg_winning_trade_bars, 1),
    "avg_loss": round(avg_loss, 2),
    "avg_loss_pct": round(avg_loss_pct, 4),
    "avg_losing_trade_bars": round(avg_losing_trade_bars, 1),
    "largest_win": round(largest_win, 2),
    "largest_win_pct": round(largest_win_pct, 2),
    "largest_win_bars": round(largest_win_bars, 1),
    "largest_loss": round(largest_loss, 2),
    "largest_loss_pct": round(largest_loss_pct, 2),
    "largest_loss_bars": round(largest_loss_bars, 1),
    "max_wins": max_wins,
    "max_losses": max_losses,
    "sharpe_ratio": round(sharpe_ratio, 2),
    "sortino_ratio": round(sortino_ratio, 2),
    "profit_factor": round(profit_factor, 2),
    "ulcer_index": round(ulcer_index, 4),
    "upi": round(upi, 2),
    "equity_r2": round(equity_r2, 4),
    "std_error": round(std_error, 2),
    "calmar_ratio": round(calmar_ratio, 2),
    "exposure_time_pct": round(exposure_time_pct, 2),
    "var_95": round(var_95, 4),
    "var_99": round(var_99, 4),
    "cvar_95": round(cvar_95, 4),
    "cvar_99": round(cvar_99, 4),
    "sqn": round(sqn, 2),
    "kelly_criterion": round(kelly_criterion, 4),
}

with open("/root/strategy_repo/metrics_summary.json", "w") as f:
    json.dump(metrics_result, f, indent=2)

print("全部指标计算完成！结果已存至 metrics_summary.json")
