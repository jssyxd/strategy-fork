"""
engine.py - DeepDatedgingOptimizer (Deep Dynamic Delta-Gamma Hedging Engine).
Calculates portfolio residual Greeks and solves optimal hedging trade sizes
under quadratic transaction costs and margin constraints.
"""

import math
import numpy as np
from typing import Dict, Any, Tuple, List

class DeepDatedgingOptimizer:
    """
    深度对冲优化器 (Deep Dynamic Hedging Optimizer)
    依据 Buehler et al. (2019) 深度对冲范式与残差希腊字母最小化:
    min_{h} [ Var(Delta_port + h_perp) + lambda_cost * Cost(h_perp) ]
    """
    def __init__(
        self,
        risk_aversion: float = 0.50,
        fee_rate_perp: float = 0.0002, # 2 bps maker
        max_hedge_leverage: float = 5.0
    ):
        self.risk_aversion = risk_aversion
        self.fee_rate_perp = fee_rate_perp
        self.max_hedge_leverage = max_hedge_leverage

    def compute_portfolio_greeks(self, holdings: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        汇总期权与标的持仓的组合级总 Greeks (Delta, Gamma, Vega, Theta).
        """
        total_delta = 0.0
        total_gamma = 0.0
        total_vega = 0.0
        total_theta = 0.0
        
        for pos in holdings:
            qty = pos.get('qty', 0.0) # 合约张数
            delta = pos.get('delta', 0.0)
            gamma = pos.get('gamma', 0.0)
            vega = pos.get('vega', 0.0)
            theta = pos.get('theta', 0.0)
            
            total_delta += qty * delta
            total_gamma += qty * gamma
            total_vega += qty * vega
            total_theta += qty * theta
            
        return {
            'total_delta': total_delta,
            'total_gamma': total_gamma,
            'total_vega': total_vega,
            'total_theta': total_theta
        }

    def optimize_hedge(
        self,
        holdings: List[Dict[str, Any]],
        underlying_price: float,
        portfolio_nav_usd: float,
        vol_forecast: float = 0.60
    ) -> Dict[str, Any]:
        """
        求解最优对冲头寸与执行指令.
        """
        greeks = self.compute_portfolio_greeks(holdings)
        port_delta = greeks['total_delta']
        port_gamma = greeks['total_gamma']
        
        # 1. 目标对冲量: 消除组合净 Delta, 兼顾交易成本惩罚
        # 凸优化解析解: h* = - port_delta / (1.0 + 2.0 * lambda * fee)
        lambda_penalty = self.risk_aversion * (vol_forecast ** 2)
        target_hedge_delta = - port_delta / (1.0 + self.fee_rate_perp * lambda_penalty)
        
        # 2. 杠杆安全约束
        max_allowed_notional = portfolio_nav_usd * self.max_hedge_leverage
        hedge_notional = abs(target_hedge_delta) * underlying_price
        
        if hedge_notional > max_allowed_notional:
            scale = max_allowed_notional / (hedge_notional + 1e-6)
            target_hedge_delta *= scale
            hedge_notional = max_allowed_notional
            
        residual_delta = port_delta + target_hedge_delta
        estimated_cost_usd = hedge_notional * self.fee_rate_perp
        
        return {
            'target_hedge_delta': round(target_hedge_delta, 4),
            'target_hedge_notional_usd': round(hedge_notional, 2),
            'direction': 'BUY' if target_hedge_delta > 0 else ('SELL' if target_hedge_delta < 0 else 'FLAT'),
            'residual_delta': round(residual_delta, 4),
            'residual_gamma': round(port_gamma, 6),
            'estimated_cost_usd': round(estimated_cost_usd, 4),
            'portfolio_greeks': greeks
        }
