"""
007 ETH AI 择时策略 - 官方 HTML 报告渲染生成器
输出：
1. backtest/alphaevolve_15m_backtest_report.html
2. backtest/dual_engine_audit_report.html
3. backtest/ablation_study_audit_report.html
"""

import os
import json
from datetime import datetime

DATA_FILE = "/home/da/桌面/回头校验eth ai timing/007_eth_ai_adaptive_sentinel/data/wfo_ablation_audit_results.json"
REPORT_DIR = "/home/da/桌面/回头校验eth ai timing/007_eth_ai_adaptive_sentinel/reports"

def generate_reports():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    wfo = data['wfo_results']
    abl = data['ablation_results']
    genome = data['best_genome']
    
    # 生成 ablation_study_audit_report.html
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>007 ETH AI 择时策略 - 全维度消融实验与 WFO 滚动审计报告</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; padding: 24px; margin: 0; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1, h2, h3 {{ color: #38bdf8; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 24px; border: 1px solid #334155; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 14px; }}
        th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ background: #0f172a; color: #94a3b8; font-weight: 600; }}
        tr:hover {{ background: #243248; }}
        .badge-pass {{ background: #065f46; color: #34d399; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: bold; }}
        .badge-fail {{ background: #7f1d1d; color: #f87171; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: bold; }}
        .badge-base {{ background: #1e3a8a; color: #60a5fa; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: bold; }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-top: 16px; }}
        .metric-box {{ background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #334155; }}
        .metric-title {{ color: #94a3b8; font-size: 12px; text-transform: uppercase; }}
        .metric-value {{ font-size: 22px; font-weight: bold; color: #38bdf8; margin-top: 6px; }}
    </style>
</head>
<body>
<div class="container">
    <h1>🚀 007 ETH AI 择时策略：动态 Walk-Forward 与六维度消融审计报告</h1>
    <p style="color: #94a3b8;">标的资产：OKX ETH-USDT-SWAP | 周期：15m | 初始资金：750.0 USDT | 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="card">
        <h2>一、 动态 Walk-Forward 滚动切片矩阵质检表 (Purged & Embargoed WFO)</h2>
        <table>
            <thead>
                <tr>
                    <th>Fold</th>
                    <th>样本内 (IS) 训练区间</th>
                    <th>样本外 (OOS) 盲测区间</th>
                    <th>OOS 收益率</th>
                    <th>OOS 最大回撤</th>
                    <th>OOS 胜率</th>
                    <th>交易笔数</th>
                    <th>Calmar</th>
                    <th>DSR 检验</th>
                    <th>四大门禁判定</th>
                </tr>
            </thead>
            <tbody>
"""
    for fold in wfo:
        g = fold['gatekeeper_report']
        pass_badge = '<span class="badge-pass">PASS 全部达标</span>' if g['all_passed'] else '<span class="badge-fail">REJECT 触发拦截</span>'
        s = fold['oos_stats']
        html_content += f"""
                <tr>
                    <td><strong>Fold {fold['fold']}</strong></td>
                    <td>{fold['is_period']}</td>
                    <td>{fold['oos_period']}</td>
                    <td style="color: {'#34d399' if s['return']>0 else '#f87171'}; font-weight: bold;">{s['return']*100:+.2f}%</td>
                    <td style="color: #f87171;">{s['mdd']*100:.2f}%</td>
                    <td>{s['win_rate']*100:.1f}%</td>
                    <td>{s['trades_cnt']} 笔</td>
                    <td>{s['calmar']:.2f}</td>
                    <td>{s['dsr']:.2f}</td>
                    <td>{pass_badge}</td>
                </tr>
"""

    html_content += f"""
            </tbody>
        </table>
    </div>

    <div class="card">
        <h2>二、 全景六维度消融实验量化评测表 (Systematic Ablation Matrix)</h2>
        <p style="color: #94a3b8;">执行法医级模块剥离与双尾 Wilcoxon 符号秩显著性检验，量化每个核心组件的边际 Alpha 贡献：</p>
        <table>
            <thead>
                <tr>
                    <th>实验代号</th>
                    <th>消融结构配置描述</th>
                    <th>累计收益率</th>
                    <th>最大回撤</th>
                    <th>胜率</th>
                    <th>夏普比率</th>
                    <th>边际贡献 (ΔSR)</th>
                    <th>显著性 (p-value)</th>
                    <th>审查结论与判定</th>
                </tr>
            </thead>
            <tbody>
"""
    for item in abl:
        badge = '<span class="badge-base">BASELINE</span>' if item['code'] == 'BASELINE' else f'<span class="badge-pass">{item["code"]}</span>'
        html_content += f"""
                <tr>
                    <td>{badge}</td>
                    <td><strong>{item['desc']}</strong></td>
                    <td style="color: {'#34d399' if item['return']>0 else '#f87171'}; font-weight: bold;">{item['return']*100:+.2f}%</td>
                    <td style="color: #f87171;">{item['mdd']*100:.2f}%</td>
                    <td>{item['win_rate']*100:.1f}%</td>
                    <td>{item['sharpe']:.2f}</td>
                    <td style="color: {'#34d399' if item['delta_sr']>=0 else '#f87171'}; font-weight: bold;">{item['delta_sr']:+.2f}</td>
                    <td>p = {item['p_value']:.4f}</td>
                    <td>{item['conclusion']}</td>
                </tr>
"""

    html_content += """
            </tbody>
        </table>
    </div>

    <div class="card">
        <h2>三、 L1~L3 三层 AI 哨兵监控看门狗状态与机制跃迁架构</h2>
        <div class="mermaid">
        stateDiagram-v2
            [*] --> Normal_Running: 系统就绪, 仓位管理正常
            Normal_Running --> L1_Alert: 滑点>5.0bps OR 时延>800ms (降级二次加仓至35%)
            L1_Alert --> Normal_Running: 滑点指标恢复
            Normal_Running --> L2_Drift: 滚动20笔胜率 < 65% OR 波动率暴涨2.5倍
            L2_Drift --> Auto_Retrain: 自动调度 WFO 滚动重训
            Auto_Retrain --> Normal_Running: 通过四大出厂门禁热更新
            Normal_Running --> L3_Circuit_Breaker: 连损3笔硬止损 OR 动态回撤>=12%
            L3_Circuit_Breaker --> Emergency_Flatten: 撤单并强制市价清仓
            Emergency_Flatten --> Lock_48H: 封锁交易网关48小时
        </div>
    </div>
</div>
<script>mermaid.initialize({startOnLoad:true, theme:'dark'});</script>
</body>
</html>
"""
    os.makedirs(REPORT_DIR, exist_ok=True)
    report_file = os.path.join(REPORT_DIR, "ablation_study_audit_report.html")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"HTML 报告已渲染成功: {report_file}")

if __name__ == "__main__":
    generate_reports()
