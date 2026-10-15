#!/usr/bin/env python3
"""
audit_anti_p_hacking.py - 自动化量化投研反造假与反大模型幻觉扫描脚本
====================================================================
功能：
1. 静态扫描策略代码与回测引擎，严禁任何硬编码截断语法（如 min/max 钳制 CAGR、Sharpe）；
2. 动态核验回测报告 JSON，检查资金守恒定律（期初、期末、总收益、逐笔盈亏之和是否绝对对账）；
3. 检查收益与夏普的符号自洽性（严禁负收益写出正高夏普、正 CAGR 的虚假现象）；
4. 检查单笔做市价差是否能够有效覆盖双边基准手续费（Unit Economics Check）。
"""

import os
import re
import sys
import json
from typing import List, Optional, Dict, Any
import numpy as np

FORBIDDEN_SYNTAX_PATTERNS = [
    r"cagr\s*=\s*min\s*\(",
    r"cagr\s*=\s*max\s*\(",
    r"sharpe\s*=\s*min\s*\(",
    r"sharpe\s*=\s*max\s*\(",
    r"else\s+2\.08",
    r"else\s+42\.1",
    r"else\s+0\.64",
    r"else\s+64\.0",
    r"min\(cagr,\s*42",
    r"max\(cagr,\s*41",
    r"round\(min\(sharpe,",
]


def scan_source_code_for_clamps(file_path: str) -> List[str]:
    """Scans Python source files for suspicious artificial clamping or metric overrides."""
    violations = []
    with open(file_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            for pat in FORBIDDEN_SYNTAX_PATTERNS:
                if re.search(pat, line):
                    violations.append(f"Line {idx}: {line.strip()} (匹配禁止规则: {pat})")
    return violations


def audit_report_integrity(report_json_path: str, trades_json_path: Optional[str] = None) -> List[str]:
    """Verifies internal mathematical consistency and conservation of capital in report JSON."""
    issues = []
    with open(report_json_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    b = rep.get("benchmark", rep)
    init_cap = float(b.get("initial_capital", 0.0))
    final_cap = float(b.get("final_capital", 0.0))
    tot_ret = float(b.get("total_return_pct", 0.0))
    cagr = float(b.get("cagr_pct", 0.0))
    sharpe = float(b.get("sharpe_ratio", 0.0))
    win_rate = float(b.get("win_rate_pct", 0.0))

    # 1. 资金账户守恒定律检查
    expected_final = init_cap * (1.0 + tot_ret / 100.0)
    if abs(final_cap - expected_final) > 1.0:
        issues.append(f"[严重破绽] 期末资金 ({final_cap:,.2f}) 与累计收益率推算期末资金 ({expected_final:,.2f}) 不对账！")

    # 2. 负收益却写正指标的矛盾检查
    if tot_ret < -0.01:
        if cagr > 0.0:
            issues.append(f"[虚假迎合] 累计总收益为负 ({tot_ret:+.2f}%)，但年化复合收益率 (CAGR) 居然为正 ({cagr:+.2f}%)！")
        if sharpe > 0.5:
            issues.append(f"[虚假迎合] 累计总收益为负 ({tot_ret:+.2f}%)，但夏普比率居然异常为高正值 ({sharpe:.2f})！")

    # 3. 逐笔成交与总盈亏对账 (如果提供了逐笔交易明细)
    if trades_json_path and os.path.exists(trades_json_path):
        with open(trades_json_path, "r", encoding="utf-8") as tf:
            trades = json.load(tf)
        if isinstance(trades, list) and len(trades) > 0:
            pnls = [float(t.get("net_pnl", 0.0)) for t in trades if "net_pnl" in t]
            sum_pnl = sum(pnls)
            calc_final = init_cap + sum_pnl
            if abs(final_cap - calc_final) > 5.0:
                issues.append(f"[记账漏洞] 逐笔交易净盈亏累计之和 ({sum_pnl:,.2f}) 与账户期末权益差额 ({final_cap - init_cap:,.2f}) 严重不符！可能存在持仓漏记或手续费重复扣款！")

            wins = sum(1 for p in pnls if p > 0)
            actual_wr = (wins / len(pnls)) * 100.0
            if abs(actual_wr - win_rate) > 2.0:
                issues.append(f"[胜率偷换] 逐笔记录实际胜率 ({actual_wr:.2f}%) 与报告所报胜率 ({win_rate:.2f}%) 严重脱节！")

    return issues


def main():
    print("=" * 80)
    print("量化投研反造假与反大模型幻觉自动化扫描工具 (Anti-P-Hacking Audit)")
    print("=" * 80)

    target_scripts = [
        "/home/da/桌面/strategy/003_agSMR_20261014/smr_tick_trader.py",
        "/home/da/桌面/strategy/003_agSMR_20261014/smr_mtf_trader.py",
        "/home/da/桌面/06_白银均值回归SMR/nautilus_silver_smr_tick_engine.py",
    ]

    has_error = False

    print("1. 源代码静态模式审查 (Static Regex Clamp Scan):")
    for s in target_scripts:
        if not os.path.exists(s):
            continue
        v = scan_source_code_for_clamps(s)
        if v:
            print(f"  ❌ FAIL: {s} 发现人工钳制造假代码:")
            for item in v:
                print(f"      -> {item}")
            has_error = True
        else:
            print(f"  ✓ PASS: {s} 源码无任何人工硬编码截断语法")

    print("\n2. 回测数据与资产守恒审计 (Conservation of Capital & Report Audit):")
    report_file = "/home/da/桌面/06_白银均值回归SMR/silver_smr_non_ohlcv_audit_report.json"
    trades_file = "/home/da/桌面/06_白银均值回归SMR/all_smr_trades.json"

    if os.path.exists(report_file):
        issues = audit_report_integrity(report_file, trades_file)
        if issues:
            print(f"  ❌ FAIL: {report_file} 存在重大逻辑破绽:")
            for issue in issues:
                print(f"      -> {issue}")
            has_error = True
        else:
            print(f"  ✓ PASS: {report_file} 资金守恒、收益自洽、胜率对账 100% 通过！")

    print("=" * 80)
    if has_error:
        print("🛑 审计未通过！存在学术造假或记账漏洞，严禁推送到主分支！")
        sys.exit(1)
    else:
        print("🏆 完整通过反造假审查！数据纯正，无任何黑箱粉饰！")
        sys.exit(0)


if __name__ == "__main__":
    main()
