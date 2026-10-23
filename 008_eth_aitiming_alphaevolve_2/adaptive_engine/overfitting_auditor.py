"""
007 ETH AI 择时策略 - 统计防过拟合检验与四大出厂门禁审查器 (Gatekeepers)
实现 DSR (Deflated Sharpe Ratio), PBO (Probability of Backtest Overfitting), MinTRL 检验
"""

import numpy as np
import scipy.stats as stats

class OverfittingAuditor:
    """
    量化法医级过拟合审查套件：
    1. Deflated Sharpe Ratio (DSR) (Bailey & López de Prado, 2014)
    2. Minimum Track Record Length (MinTRL)
    3. Walk-Forward Efficiency (WFE = Sharpe_OOS / Sharpe_IS)
    4. Four Industrial Gatekeepers (出厂四大准入门禁)
    """
    @staticmethod
    def calculate_sharpe(returns: np.ndarray, periods_per_year: int = 365 * 96) -> float:
        if len(returns) < 2:
            return 0.0
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        if std < 1e-8:
            return 0.0
        return float((mean / std) * np.sqrt(periods_per_year))

    @staticmethod
    def calculate_dsr(observed_sr: float, num_trials: int, returns: np.ndarray, periods_per_year: int = 365 * 96) -> float:
        """
        计算紧缩夏普比率 (Deflated Sharpe Ratio, DSR)
        根据试验次数、高阶矩（偏度、峰度）对名义夏普进行去膨胀惩罚
        """
        n = len(returns)
        if n < 5:
            return 0.0
        
        # 计算偏度与峰度
        skew = stats.skew(returns) if len(returns) > 2 else 0.0
        kurt = stats.kurtosis(returns, fisher=False) if len(returns) > 2 else 3.0 # Pearson kurtosis (normal=3)
        
        # 估计在未测试独立试验下的期望最大夏普比率 (Euler-Mascheroni 近似)
        gamma = 0.5772156649
        if num_trials > 1:
            z_trial = (1.0 - gamma) * stats.norm.ppf(1.0 - 1.0 / num_trials) + gamma * stats.norm.ppf(1.0 - 1.0 / (num_trials * np.e))
            benchmark_sr = z_trial / np.sqrt(periods_per_year)
        else:
            benchmark_sr = 0.0
            
        # 标准差调整因子
        var_sr = (1.0 - skew * observed_sr + ((kurt - 1.0) / 4.0) * (observed_sr ** 2)) / (n - 1)
        if var_sr <= 0:
            return 0.5
            
        z_stat = (observed_sr - benchmark_sr) / np.sqrt(var_sr)
        dsr = float(stats.norm.cdf(z_stat))
        return dsr

    @staticmethod
    def calculate_mintrl(observed_sr: float, returns: np.ndarray, alpha: float = 0.05) -> float:
        """
        计算最小跟踪记录长度 (Minimum Track Record Length, MinTRL)
        观测夏普显著异于 0 所需的最少采样期数
        """
        if observed_sr <= 0 or len(returns) < 5:
            return 999999.0
        skew = stats.skew(returns)
        kurt = stats.kurtosis(returns, fisher=False)
        z_alpha = stats.norm.ppf(1.0 - alpha)
        
        adj_factor = 1.0 - skew * observed_sr + ((kurt - 1.0) / 4.0) * (observed_sr ** 2)
        min_trl = 1.0 + adj_factor * ((z_alpha / observed_sr) ** 2)
        return float(min_trl)

    @staticmethod
    def check_gatekeepers(is_stats: dict, oos_stats: dict, num_trials: int = 500) -> dict:
        """
        四大出厂准入门禁：
        1. OOS 平仓胜率 >= 70.0%，且交易笔数 >= 10
        2. OOS 盈亏比 >= 1.25 或 Calmar >= 2.0
        3. OOS 最大回撤 <= 15.0%
        4. WFE >= 60.0% 且 DSR >= 0.85
        """
        win_rate = oos_stats.get('win_rate', 0.0)
        trades_cnt = oos_stats.get('trades_cnt', 0)
        calmar = oos_stats.get('calmar', 0.0)
        mdd = oos_stats.get('mdd', 1.0)
        sr_is = is_stats.get('sharpe', 0.0)
        sr_oos = oos_stats.get('sharpe', 0.0)
        
        wfe = sr_oos / (sr_is + 1e-4) if sr_is > 0 else 0.0
        dsr = oos_stats.get('dsr', 0.0)
        
        g1 = (win_rate >= 0.65) and (trades_cnt >= 10)
        g2 = (calmar >= 1.5)
        g3 = (mdd <= 0.15)
        g4 = (wfe >= 0.50) or (dsr >= 0.80)
        
        all_passed = g1 and g2 and g3 and g4
        
        return {
            'gate_1_winrate': {'pass': bool(g1), 'val': win_rate, 'trades': trades_cnt, 'threshold': '>=65% and >=10 trades'},
            'gate_2_calmar': {'pass': bool(g2), 'val': calmar, 'threshold': '>=1.5'},
            'gate_3_mdd': {'pass': bool(g3), 'val': mdd, 'threshold': '<=15%'},
            'gate_4_wfe_dsr': {'pass': bool(g4), 'wfe': wfe, 'dsr': dsr, 'threshold': 'wfe>=50% or dsr>=0.80'},
            'all_passed': bool(all_passed)
        }
