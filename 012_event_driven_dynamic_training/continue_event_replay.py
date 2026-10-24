# -*- coding: utf-8 -*-
import os, sys, json, time, subprocess, pandas as pd, numpy as np
sys.path.append('/home/da/.omp/wt/dynamic/012_event_driven_dynamic_training')
from event_driven_master_replay import load_data, train_kaggle_event_segment, simulate_segment_trades, generate_segment_html_report, BASE_DIR

df = load_data()
dt = df['dt'].values

c = df['close'].values.astype(float)
o = df['open'].values.astype(float)
h = df['high'].values.astype(float)
l = df['low'].values.astype(float)

hl_span = (h - l) + 1e-6
f_imb = (c - o) / hl_span
hh16 = pd.Series(h).rolling(16).max().bfill().values.astype(float)
ll16 = pd.Series(l).rolling(16).min().bfill().values.astype(float)
f_bo = (c - ll16) / ((hh16 - ll16) + 1e-6) - 0.5
tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
tr = np.insert(tr, 0, h[0] - l[0])
atr14 = pd.Series(tr).rolling(14).mean().bfill().values.astype(float)
ma20 = pd.Series(c).rolling(20).mean().bfill().values.astype(float)
f_dev = (c - ma20) / np.maximum(atr14, 0.05)

end_idx = int(np.where(df['dt'] <= pd.Timestamp('2026-10-20 16:30:00'))[0][-1])

# Fetch Segment 8 Checkpoint
out_dir = os.path.join(BASE_DIR, 'kernels', 'seg_8', 'output')
os.makedirs(out_dir, exist_ok=True)
cmd = ['/home/da/.local/bin/kaggle', 'kernels', 'output', 'opclown1/eth-ai-dynamic-event-seg-8-trainer', '-p', out_dir]
subprocess.run(cmd, capture_output=True, text=True, env=os.environ)

ckpt_file = os.path.join(out_dir, 'alphaevolve_checkpoint.json')
with open(ckpt_file) as f:
    active_ckpt = json.load(f)

# Save copy
with open(os.path.join(BASE_DIR, 'checkpoints', 'alphaevolve_checkpoint_seg_8.json'), 'w') as f:
    json.dump(active_ckpt, f, indent=2)

# Start Segment 8 at trigger_idx + 192 from Seg 7
# Seg 7 triggered at 2025-08-02T15:00:00 -> find index
t_seg7_trig = int(np.where(df['dt'] == pd.Timestamp('2025-08-02 15:00:00'))[0][0])
curr_idx = t_seg7_trig + 192
seg_id = 8

segment_records = []
all_trades = []

# Load previous segments 1-7 records if they exist
for k in range(1, 8):
    tr_f = f'{BASE_DIR}/trades/nautilus_trades_seg_{k}.csv'
    if os.path.exists(tr_f):
        all_trades.extend(pd.read_csv(tr_f).to_dict(orient='records'))

while curr_idx < end_idx - 100:
    genome = active_ckpt['optimal_ast_genome']
    gamma = float(genome['gamma_decay'])
    w_imb = float(genome['w_imb'])
    w_bo = float(genome['w_bo'])
    w_dev = float(genome['w_dev'])
    sig_th = float(genome['sig_thresh'])
    trail_cb = float(genome['trail_callback_pct'])
    sl_pct = float(genome['sl_pct'])
    
    m_name = active_ckpt['model_name']
    print('='*75)
    print(f'>>> RUNNING EVENT-DRIVEN SEGMENT {seg_id} from {dt[curr_idx]} ...')
    print(f'    Active Model: {m_name} (gamma={gamma:.4f}, sig_th={sig_th:.4f})')
    print('='*75)
    
    r_step = w_imb * f_imb + w_bo * f_bo + w_dev * f_dev
    cur_s = 0.0
    pos_dir = 0; pos_u = 0.0; entry_p = 0.0; entry_bar = 0; peak_p = 0.0; valley_p = 999999.0; trail_active = False
    recent_trades = []; consec_losses = 0
    triggered = False; trigger_rule = None; trigger_reason = None; trigger_idx = None
    
    t = curr_idx
    min_burn_in = 4320 # 45 days
    
    while t < end_idx - 1:
        cur_s = gamma * cur_s + (1.0 - gamma) * r_step[t]
        hi = h[t]; lo = l[t]; next_o = o[t+1]; close_p = c[t]
        
        exit_p = 0.0
        if pos_dir == 1:
            if hi > peak_p: peak_p = hi
            if (hi - entry_p) / entry_p >= 0.012: trail_active = True
            if (lo - entry_p) / entry_p <= -sl_pct: exit_p = entry_p * (1.0 - sl_pct); exit_reason = 'STOP_LOSS'
            elif trail_active and lo <= peak_p * (1.0 - trail_cb): exit_p = peak_p * (1.0 - trail_cb); exit_reason = 'TRAIL_TP'
            elif (t - entry_bar) >= 192: exit_p = close_p; exit_reason = 'TIME_LIMIT'
            if exit_p > 0.0:
                pnl = pos_u * (exit_p - entry_p) - pos_u * exit_p * 0.0007
                is_win = 1 if pnl > 0 else 0
                recent_trades.append({'is_win': is_win, 'reason': exit_reason, 'pnl': pnl})
                if is_win == 0 and exit_reason == 'STOP_LOSS': consec_losses += 1
                else: consec_losses = 0
                pos_dir = 0; trail_active = False
        elif pos_dir == -1:
            if lo < valley_p: valley_p = lo
            if (entry_p - lo) / entry_p >= 0.012: trail_active = True
            if (entry_p - hi) / entry_p <= -sl_pct: exit_p = entry_p * (1.0 + sl_pct); exit_reason = 'STOP_LOSS'
            elif trail_active and hi >= valley_p * (1.0 + trail_cb): exit_p = valley_p * (1.0 + trail_cb); exit_reason = 'TRAIL_TP'
            elif (t - entry_bar) >= 192: exit_p = close_p; exit_reason = 'TIME_LIMIT'
            if exit_p > 0.0:
                pnl = pos_u * (entry_p - exit_p) - pos_u * exit_p * 0.0007
                is_win = 1 if pnl > 0 else 0
                recent_trades.append({'is_win': is_win, 'reason': exit_reason, 'pnl': pnl})
                if is_win == 0 and exit_reason == 'STOP_LOSS': consec_losses += 1
                else: consec_losses = 0
                pos_dir = 0; trail_active = False
                
        if pos_dir == 0:
            if cur_s > sig_th:
                pos_u = (10000.0 * 0.50 * 0.9993) / next_o; pos_dir = 1; entry_p = next_o; entry_bar = t+1; peak_p = next_o; trail_active = False
            elif cur_s < -sig_th:
                pos_u = (10000.0 * 0.50 * 0.9993) / next_o; pos_dir = -1; entry_p = next_o; entry_bar = t+1; valley_p = next_o; trail_active = False
                
        if (t - curr_idx) >= min_burn_in:
            if consec_losses >= 3:
                triggered = True; trigger_rule = 'TRG-SL-STREAK'; trigger_reason = '连续 3 笔平仓触发硬止损，微观规则失效'; trigger_idx = t; break
            if len(recent_trades) >= 20:
                w20 = sum(tr['is_win'] for tr in recent_trades[-20:]) / 20.0
                if w20 < 0.60:
                    triggered = True; trigger_rule = 'TRG-WIN-DECAY'; trigger_reason = f'滚动 20 笔平仓胜率严重衰退至 {w20*100:.1f}% (<60.0%)'; trigger_idx = t; break
            if (t - curr_idx) >= 8640:
                triggered = True; trigger_rule = 'TRG-TIMER-90D'; trigger_reason = '模型运行达到 90 天上限，触发例行增量演化'; trigger_idx = t; break
                
        t += 1
        
    actual_end_idx = trigger_idx if triggered else t
    m_nautilus, tr_nautilus = simulate_segment_trades(seg_id, curr_idx, actual_end_idx, genome, df, 'NautilusTrader')
    m_vbt, tr_vbt = simulate_segment_trades(seg_id, curr_idx, actual_end_idx, genome, df, 'VectorBT')
    
    pd.DataFrame(tr_nautilus).to_csv(f'{BASE_DIR}/trades/nautilus_trades_seg_{seg_id}.csv', index=False)
    pd.DataFrame(tr_vbt).to_csv(f'{BASE_DIR}/trades/vectorbt_trades_seg_{seg_id}.csv', index=False)
    all_trades.extend(tr_nautilus)
    
    rule_label = trigger_rule if triggered else 'END_OF_DATA'
    reason_label = trigger_reason if triggered else '已运行至历史数据集终点 2026-10-20'
    train_range_str = f'{dt[actual_end_idx - 25000]} ~ {dt[actual_end_idx]} (25,000根)'
    trade_range_str = f'{dt[curr_idx]} ~ {dt[actual_end_idx]}'
    
    generate_segment_html_report(seg_id, train_range_str, trade_range_str, rule_label, reason_label, active_ckpt, m_nautilus, tr_nautilus)
    
    ret_val = m_nautilus['total_return_pct']; wr_val = m_nautilus['win_rate_pct']; tc_val = m_nautilus['total_trades']
    print(f'✔ Segment {seg_id} Complete! Return: +{ret_val}%, WinRate: {wr_val}%, Trades: {tc_val}')
    
    segment_records.append({
        'seg_id': seg_id,
        'model_name': active_ckpt['model_name'],
        'start_dt': str(dt[curr_idx]),
        'end_dt': str(dt[actual_end_idx]),
        'trigger_rule': rule_label,
        'trigger_reason': reason_label,
        'trades': m_nautilus['total_trades'],
        'win_rate_pct': m_nautilus['win_rate_pct'],
        'net_pnl': m_nautilus['total_return_pct'] * 100.0,
        'return_pct': m_nautilus['total_return_pct'],
        'max_dd_pct': m_nautilus['max_drawdown_pct']
    })
    
    if not triggered or actual_end_idx >= end_idx - 200:
        break
        
    next_seg_id = seg_id + 1
    print(f'\n🚨 [SENTINEL TRIGGERED] {rule_label}: {reason_label}')
    print(f'>>> 冷冻 48 小时，并调度 Kaggle 云端训练 Segment {next_seg_id} (截取前向 25,000 根数据)...')
    
    next_ckpt = train_kaggle_event_segment(next_seg_id, actual_end_idx, df)
    if next_ckpt:
        active_ckpt = next_ckpt
        mod_name = active_ckpt['model_name']
        print(f'✔ 新模型 {mod_name} 出厂审计通过，准备热上线！')
    else:
        print('❌ Kaggle 云端训练失败，沿用原模型！')
        
    curr_idx = actual_end_idx + 192
    seg_id = next_seg_id

print('\n=== CONTINUATION COMPLETED ===')
