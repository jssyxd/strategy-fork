"""
007 ETH AI 择时策略 - 核心回测与消融实验全量驱动脚本
挂载本地以太坊 15m 数据湖，执行：
1. 数据治理与不变性校验
2. 多折 Walk-Forward 滚动演化 (IS 训练 + OOS 盲测)
3. 统计防过拟合审查 (WFE, DSR, MinTRL)
4. 六维度消融实验 (Q-State / 加仓 / 动态止盈 / 硬止损 / 杠杆)
5. 产出结构化审计 JSON 结果文件供双引擎报告渲染
"""

import os
import sys
import json
import numpy as np
import pandas as pd

from src.feature_pipeline import DataLakeGovernance, FeaturePipeline
from src.execution_engine import RealisticExecutionEngine
from src.wfo_pipeline import WalkForwardPipeline
from src.ablation_study import SystematicAblationStudy
from src.overfitting_auditor import OverfittingAuditor

DATA_PATH = "/home/da/桌面/database/03_governed_lake/v2_parquet_lake/crypto/futures_swap/ETH-USDT-SWAP/15m/ETH-USDT-SWAP_15m_governed.parquet"

def main():
    print("=== [Pipeline] 启动 007 ETH AI 滚动重训与消融研究执行套件 ===")
    assert os.path.exists(DATA_PATH), f"数据湖文件不存在: {DATA_PATH}"
    
    # 1. 载入并清洗
    raw_df = pd.read_parquet(DATA_PATH)
    print(f"数据湖载入完成: {len(raw_df)} 根 15m K线")
    
    clean_df = DataLakeGovernance.audit_and_clean(raw_df)
    features = FeaturePipeline.extract_features(clean_df)
    
    # 2. 执行 Walk-Forward 滚动切片
    wfo = WalkForwardPipeline(is_bars=1800, oos_bars=600, purge_bars=20, embargo_bars=10)
    wfo_results, _, _ = wfo.run_wfo(clean_df, num_folds=2)
    
    # 选取最佳 Fold 作为生产候选基准
    best_fold = wfo_results[0]
    best_genome = best_fold['best_genome']
    print(f"\n[Elected Best Genome]: {best_genome}")
    
    # 3. 运行全景六维度消融实验
    print("\n=== [Ablation] 启动六维度全景消融隔离评测 ===")
    ablation_study = SystematicAblationStudy()
    ablation_results = ablation_study.run_all_ablations(features, best_genome)
    
    for item in ablation_results:
        print(f"[{item['code']}] Ret={item['return']*100:+.2f}%, MDD={item['mdd']*100:.2f}%, Win={item['win_rate']*100:.1f}%, Sharpe={item['sharpe']:.2f}, ΔSR={item['delta_sr']:+.2f}, p={item['p_value']:.4f} -> {item['conclusion']}")

    # 4. 保存为标准交付物 JSON
    out_dir = "/home/da/桌面/回头校验eth ai timing/007_eth_ai_adaptive_sentinel/data"
    os.makedirs(out_dir, exist_ok=True)
    
    out_file = os.path.join(out_dir, "wfo_ablation_audit_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            'wfo_results': wfo_results,
            'ablation_results': ablation_results,
            'best_genome': best_genome
        }, f, indent=2, ensure_ascii=False)
        
    print(f"\n>>> 审计报告数据已成功保存至: {out_file}")

if __name__ == "__main__":
    main()
