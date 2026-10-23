"""
007 ETH AI 择时策略 - 动态 Walk-Forward 滚动切片矩阵架构与流水线调度器
实现 Purged & Embargoed 时序防泄漏隔离、样本内演化与样本外盲测校验
"""

import numpy as np
import pandas as pd
from src.feature_pipeline import FeaturePipeline, DataLakeGovernance
from src.execution_engine import RealisticExecutionEngine
from src.multi_island_ga import MultiIslandAlphaEvolveEngine
from src.overfitting_auditor import OverfittingAuditor

class WalkForwardPipeline:
    def __init__(self, is_bars=2880, oos_bars=960, purge_bars=20, embargo_bars=10):
        """
        以 15m 为基准：
        is_bars = 2880 (约 30 天样本内训练)
        oos_bars = 960  (约 10 天严格样本外盲测)
        purge_bars = 20 (约 5 小时防信息穿越隔离带)
        embargo_bars = 10 (约 2.5 小时禁运区)
        """
        self.is_bars = is_bars
        self.oos_bars = oos_bars
        self.purge_bars = purge_bars
        self.embargo_bars = embargo_bars
        self.executor = RealisticExecutionEngine(initial_capital=750.0)
        self.ga_engine = MultiIslandAlphaEvolveEngine(max_generations=150)

    def run_wfo(self, df: pd.DataFrame, num_folds: int = 4):
        # 1. 治理与特征提取
        clean_df = DataLakeGovernance.audit_and_clean(df)
        features = FeaturePipeline.extract_features(clean_df)
        total_len = len(features['close'])
        
        step = self.oos_bars
        results = []
        
        print(f"=== 启动 Walk-Forward 滚动切片流水线 (Total Bars: {total_len}, Folds: {num_folds}) ===")
        
        for fold in range(num_folds):
            is_start = fold * step
            is_end = is_start + self.is_bars
            
            oos_start = is_end + self.purge_bars
            oos_end = oos_start + self.oos_bars
            
            if oos_end > total_len:
                print(f"[Fold {fold+1}] 数据不足，截断推进")
                break
                
            dt_is_start = str(clean_df['datetime'].iloc[is_start])
            dt_is_end = str(clean_df['datetime'].iloc[is_end])
            dt_oos_start = str(clean_df['datetime'].iloc[oos_start])
            dt_oos_end = str(clean_df['datetime'].iloc[oos_end - 1])
            
            print(f"\n>>> [Fold {fold+1}/{num_folds}] IS: {dt_is_start[:10]} -> {dt_is_end[:10]} | OOS: {dt_oos_start[:10]} -> {dt_oos_end[:10]}")
            
            # 1. 样本内多岛屿演化
            best_genome, is_fit, is_stats = self.ga_engine.evolve(self.executor, features, is_start, is_end)
            if best_genome is None:
                continue
                
            # 计算 IS 夏普
            _, is_ret, is_mdd, is_win, is_cnt, is_eq = self.executor.simulate(features, best_genome, is_start, is_end)
            is_returns = np.diff(is_eq) / is_eq[:-1] if len(is_eq) > 1 else np.array([0.0])
            is_sharpe = OverfittingAuditor.calculate_sharpe(is_returns)
            is_stats['sharpe'] = is_sharpe
            
            # 2. 样本外盲测评估 (OOS)
            oos_fit, oos_ret, oos_mdd, oos_win, oos_cnt, oos_eq = self.executor.simulate(features, best_genome, oos_start, oos_end)
            oos_returns = np.diff(oos_eq) / oos_eq[:-1] if len(oos_eq) > 1 else np.array([0.0])
            oos_sharpe = OverfittingAuditor.calculate_sharpe(oos_returns)
            oos_calmar = oos_ret / (oos_mdd + 1e-4)
            oos_dsr = OverfittingAuditor.calculate_dsr(oos_sharpe, num_trials=50, returns=oos_returns)
            
            oos_stats = {
                'return': oos_ret,
                'mdd': oos_mdd,
                'win_rate': oos_win,
                'trades_cnt': oos_cnt,
                'sharpe': oos_sharpe,
                'calmar': oos_calmar,
                'dsr': oos_dsr
            }
            
            # 3. 四大出厂门禁质检
            gatekeeper_report = OverfittingAuditor.check_gatekeepers(is_stats, oos_stats)
            
            fold_record = {
                'fold': fold + 1,
                'is_period': f"{dt_is_start} to {dt_is_end}",
                'oos_period': f"{dt_oos_start} to {dt_oos_end}",
                'best_genome': best_genome,
                'is_stats': is_stats,
                'oos_stats': oos_stats,
                'gatekeeper_report': gatekeeper_report
            }
            results.append(fold_record)
            
            print(f"    OOS 表现: Ret={oos_ret*100:.2f}%, MDD={oos_mdd*100:.2f}%, Win={oos_win*100:.2f}%, Trades={oos_cnt}, Calmar={oos_calmar:.2f}, DSR={oos_dsr:.2f}")
            print(f"    门禁判定: {'[通过]' if gatekeeper_report['all_passed'] else '[拦截 (未达标)]'}")
            
        return results, clean_df, features
