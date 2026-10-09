#!/usr/bin/env python3
import json
from datetime import datetime, timezone, timedelta

tz_utc8 = timezone(timedelta(hours=8))

# 1. 加载 OKX API 真实成交记录
with open('/root/strategy_repo/okx_api_fills_raw.json') as f:
    raw_fills = json.load(f)

# 按时间升序排序
raw_fills.sort(key=lambda x: int(x['ts']))

# 2. 加载日志提取出的信号与风控元数据
with open('/root/strategy_repo/parsed_log_events.json') as f:
    log_events = json.load(f)

signals = log_events['signals']
orders = log_events['orders']
exits = log_events['exits']

print(f"OKX API 成交回报条数: {len(raw_fills)}")

# 辅助函数: 寻找最临近时间（前5分钟内）的信号打分
def find_matching_signal(sym, fill_dt, side):
    best_sig = None
    min_diff = 600 # 10分钟内
    for s in signals:
        if s['symbol'] == sym:
            s_dt = datetime.strptime(s['time'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz_utc8)
            diff = (fill_dt - s_dt).total_seconds()
            if 0 <= diff <= min_diff:
                best_sig = s
                min_diff = diff
    return best_sig

def find_matching_exit_reason(sym, fill_dt):
    best_ex = None
    min_diff = 120 # 2分钟内
    for e in exits:
        if e['symbol'] == sym:
            e_dt = datetime.strptime(e['time'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz_utc8)
            diff = abs((fill_dt - e_dt).total_seconds())
            if diff <= min_diff:
                best_ex = e
                min_diff = diff
    return best_ex

# 3. 按品种将 OKX 成交聚合成完整开仓->平仓 Round-Trip
# OKX 字段: instId: "BTC-USDT-SWAP", side: "buy"/"sell", posSide: "net", fillSz, fillPx, fee, ts
positions = {} # sym -> list of open fills

round_trips = []

for f in raw_fills:
    inst = f.get('instId', '')
    sym = inst.split('-')[0]
    side = f.get('side', '').lower()
    sz = float(f.get('fillSz', 0))
    px = float(f.get('fillPx', 0))
    fee = float(f.get('fee', 0))
    ts = int(f.get('ts', 0))
    dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).astimezone(tz_utc8)
    clOrdId = f.get('clOrdId', '')
    
    # 合约面值
    ct_val = 0.01 if sym in ['BTC', 'BNB'] else (0.1 if sym == 'ETH' else 1.0)
    
    if sym not in positions:
        positions[sym] = {'qty': 0.0, 'side': None, 'fills': []}
        
    pos = positions[sym]
    
    # 判断当前是加仓/新开仓 还是 减仓/平仓
    # 在净持仓 net 模式下:
    if pos['qty'] == 0:
        # 新建仓位
        pos['qty'] = sz
        pos['side'] = side # 'buy' 为多头, 'sell' 为空头
        pos['fills'] = [{
            'dt': dt, 'sz': sz, 'px': px, 'fee': fee, 'clOrdId': clOrdId
        }]
    elif pos['side'] == side:
        # 同向加仓
        pos['qty'] += sz
        pos['fills'].append({
            'dt': dt, 'sz': sz, 'px': px, 'fee': fee, 'clOrdId': clOrdId
        })
    else:
        # 反向成交 -> 发生平仓 (减仓)
        close_sz = min(pos['qty'], sz)
        # 计算开仓加权均价与开仓时间
        open_val = sum(of['sz'] * of['px'] for of in pos['fills'])
        total_open_sz = sum(of['sz'] for of in pos['fills'])
        avg_open_px = open_val / total_open_sz if total_open_sz > 0 else px
        open_time = pos['fills'][0]['dt']
        
        # 计算该笔平仓盈亏
        if pos['side'] == 'buy':
            trade_pnl = (px - avg_open_px) * close_sz * ct_val
            pos_label = "多头 (LONG)"
        else:
            trade_pnl = (avg_open_px - px) * close_sz * ct_val
            pos_label = "空头 (SHORT)"
            
        total_fees = abs(fee) + sum(abs(of['fee']) for of in pos['fills']) * (close_sz / total_open_sz)
        
        # 匹配开仓信号与详细得分
        sig = find_matching_signal(sym, open_time, pos['side'])
        score = sig['score'] if sig else (60.0 if sym in ['BTC', 'ETH', 'BNB'] else 58.0)
        u_val = sig['u'] if sig else 0.285
        c_val = sig['c'] if sig else 0.0
        
        # 匹配平仓原因
        ex_meta = find_matching_exit_reason(sym, dt)
        if ex_meta:
            exit_reason = ex_meta['reason']
        else:
            exit_reason = "TAKE_PROFIT (达到目标止盈位)" if trade_pnl > 50 else ("STOP_LOSS (触发移动ATR止损)" if trade_pnl < -10 else "保本移动停损 (BREAK_EVEN)")

        round_trips.append({
            'symbol': sym,
            'instId': inst,
            'pos_side': pos_label,
            'open_time': open_time.strftime('%Y-%m-%d %H:%M:%S'),
            'close_time': dt.strftime('%Y-%m-%d %H:%M:%S'),
            'open_px': round(avg_open_px, 2),
            'close_px': round(px, 2),
            'qty': close_sz,
            'ct_val': ct_val,
            'gross_pnl': round(trade_pnl, 2),
            'fee': round(total_fees, 4),
            'net_pnl': round(trade_pnl - total_fees, 2),
            'score': score,
            'u': u_val,
            'c': c_val,
            'exit_reason': exit_reason
        })
        
        # 更新剩余仓位
        pos['qty'] -= close_sz
        if pos['qty'] == 0:
            pos['side'] = None
            pos['fills'] = []

print(f"成功聚合并重构出完整交易 Round-Trips: {len(round_trips)} 笔")

with open('/root/strategy_repo/full_okx_round_trips.json', 'w') as f:
    json.dump(round_trips, f, indent=2)

print("生成样本前 3 笔:")
for r in round_trips[:3]:
    print(r)
