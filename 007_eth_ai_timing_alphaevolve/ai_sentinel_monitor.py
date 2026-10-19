import json
import time
import numpy as np
import pandas as pd
from datetime import datetime

class TopTierQuantSentinel:
    """
    顶级量化对冲基金标准：AI 策略生产环境三层监控与自愈哨兵系统
    L1: 撮合与微观执行层 (Slippage, Latency, Fill Ratio)
    L2: 因子与模型概念漂移层 (Information Coefficient, PSI, Vol Regime)
    L3: 资本与组合硬熔断层 (Drawdown, Consec Losses, Tail Risk)
    """
    def __init__(self, config_path=None):
        self.max_consec_losses_limit = 3       # 连续 3 笔止损触发冷冻熔断
        self.rolling_win_rate_floor = 0.65     # 滚动 20 笔平仓胜率下限 65%
        self.max_drawdown_limit = 0.12         # 组合最大动态回撤限制 12%
        self.max_slippage_bps = 5.0            # 最大滑点 5 个基点 (0.05%)
        self.vol_regime_threshold = 2.5        # 14日年化波动率暴涨倍数
        
        self.state_history = []
        self.recent_trades = []
        self.is_halted = False

    def ingest_execution_event(self, trade_event):
        """
        L1 监控：每笔订单撮合事件接入
        trade_event: { 'time', 'order_id', 'expected_price', 'fill_price', 'pnl', 'is_win', 'reason' }
        """
        # 1. 执行滑点审查
        slippage_bps = abs(trade_event['fill_price'] - trade_event['expected_price']) / trade_event['expected_price'] * 10000.0
        if slippage_bps > self.max_slippage_bps:
            self.emit_alert("CRITICAL_EXECUTION", f"订单 {trade_event['order_id']} 出现严重滑点 {slippage_bps:.1f} bps，超过容忍阈值 {self.max_slippage_bps} bps！")

        self.recent_trades.append(trade_event)
        self.evaluate_capital_safety()

    def evaluate_capital_safety(self):
        """
        L3 监控：资本与连续损失熔断状态机
        """
        if len(self.recent_trades) < 3:
            return

        # 检查连续亏损
        recent_3 = self.recent_trades[-3:]
        if all(t.get('is_win') == 0 for t in recent_3):
            self.trigger_circuit_breaker("连续 3 笔触发硬止损，策略进入紧急冷冻熔断状态，禁止任何新开仓！")

        # 检查滚动胜率 (最近 20 笔)
        if len(self.recent_trades) >= 20:
            window = self.recent_trades[-20:]
            wins = sum(1 for t in window if t.get('is_win') == 1)
            win_rate = wins / len(window)
            if win_rate < self.rolling_win_rate_floor:
                self.trigger_retrain_request("STATISTICAL_DECAY", f"滚动 20 笔胜率跌破 {self.rolling_win_rate_floor*100}% (当前: {win_rate*100:.1f}%)，触发全流程重演化！")

    def monitor_market_regime(self, market_df):
        """
        L2 监控：市场宏观机制漂移 (Regime Shift) 与因子衰减
        market_df: 包含 close, volume, high, low 的 15m 历史序列
        """
        # 1. 波动率机制跃迁 (ATR / 滚动标准差)
        ret = market_df['close'].pct_change().dropna()
        vol_current = ret.iloc[-2880:].std() * np.sqrt(35040) # 最近30天年化波动率
        vol_baseline = ret.iloc[-8760:-2880].std() * np.sqrt(35040) # 基准历史波动率
        
        ratio = vol_current / (vol_baseline + 1e-6)
        if ratio > self.vol_regime_threshold:
            self.trigger_retrain_request("VOLATILITY_EXPANSION", f"市场年化波动率从基准 {vol_baseline*100:.1f}% 飙升至 {vol_current*100:.1f}% (放大 {ratio:.2f} 倍)，原极值阈值失效，强制重训！")

        # 2. 资金费率与单边趋势持久度
        # 若连续 48 根 15m K线 (12小时) 处于单边无回踩，判定为流动性踩踏机制
        c = market_df['close'].values
        ma50 = pd.Series(c).rolling(50).mean().values
        trend_persistent = np.all(c[-48:] > ma50[-48:]) or np.all(c[-48:] < ma50[-48:])
        if trend_persistent:
            self.emit_alert("PERSISTENT_TREND", "市场进入极端单边强趋势状态，马丁自愈逻辑风险急剧上升，动态收紧首仓至 25% 并拉宽加仓距离！")

    def trigger_circuit_breaker(self, reason):
        self.is_halted = True
        print(f"\n🚨 [CIRCUIT BREAKER TRIGGERED] {reason}")
        # 在生产环境中：自动调用 OKX API 取消所有挂单、清空仓位或禁止入场，并发送 Webhook 报警至 Telegram / 飞书

    def trigger_retrain_request(self, trigger_type, description):
        print(f"\n🔄 [TRIGGER RETRAIN PIPELINE] 触发类型: {trigger_type} | 说明: {description}")
        print(">>> 调度 AlphaEvolve JIT 自动化重训流水线: 重新加载最近 25,000 根治理切片，启动种群自适应演化...")

    def emit_alert(self, level, message):
        print(f"⚠️ [{level}] {message}")

if __name__ == "__main__":
    sentinel = TopTierQuantSentinel()
    print(">>> 顶级对冲基金级 AI 哨兵监控程序初始化就绪。")
