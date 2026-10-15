"""
Execution, Cross-Channel Routing (Spot & Perp), and Backtest Engine.
Incorporates Almgren-Chriss / Kyle square-root market impact for 15M CNY capacity,
perpetual funding rate cash-flow settlements, and realistic taker/maker fee schedules.
"""

import numpy as np

class BacktestEngine:
    def __init__(
        self,
        initial_capital_cny=15000000.0, # 1500万 CNY
        cny_usd_rate=7.20,
        perp_maker_fee=0.0002,          # 2 bps
        perp_taker_fee=0.0005,          # 5 bps
        spot_maker_fee=0.00075,         # 7.5 bps
        spot_taker_fee=0.0010,          # 10 bps
        max_leverage=2.5,
        stop_loss_pct=0.022,            # 2.2% hard stop
        take_profit_trailing_pct=0.038, # 3.8% trailing take profit
        entry_threshold=0.20,
        burst_threshold=0.30,
        leverage_scale=2.2,
        bars_per_year=365 * 288         # 5-minute bars per year
    ):
        self.initial_capital_usd = initial_capital_cny / cny_usd_rate
        self.initial_capital_cny = initial_capital_cny
        self.cny_usd_rate = cny_usd_rate
        
        self.perp_maker_fee = perp_maker_fee
        self.perp_taker_fee = perp_taker_fee
        self.spot_maker_fee = spot_maker_fee
        self.spot_taker_fee = spot_taker_fee
        
        self.max_leverage = max_leverage
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_trailing_pct = take_profit_trailing_pct
        self.entry_threshold = entry_threshold
        self.burst_threshold = burst_threshold
        self.leverage_scale = leverage_scale
        self.bars_per_year = bars_per_year

    def calculate_market_impact_slippage(self, order_usd, bar_volume_usd, bar_volatility):
        """
        Square-root law of market impact:
        Slippage = HalfSpread + eta * sigma * sqrt(OrderSize / BarVolume)
        Ensures 15M CNY capacity realistically incurs friction.
        """
        half_spread_bps = 0.00015 # 1.5 bps tight DOGE top-tier liquidity
        participation_rate = np.clip(order_usd / (bar_volume_usd + 1e-8), 0.0001, 0.25)
        impact_bps = 0.5 * bar_volatility * np.sqrt(participation_rate)
        total_slippage = half_spread_bps + impact_bps
        return total_slippage

    def run_backtest(self, df_dict, signals, burst_confs):
        """
        Simulates sequential high-frequency trading with spot/perp routing.
        """
        perp_prices = df_dict['perp_close']
        spot_prices = df_dict['spot_close']
        volumes_usd = df_dict['volume'] * perp_prices
        funding_rates = df_dict['funding_rate']
        
        n_bars = len(perp_prices)
        cash = self.initial_capital_usd
        equity_curve = np.zeros(n_bars)
        equity_curve[0] = cash
        
        position_size_coin = 0.0 # positive = long, negative = short
        position_channel = None  # 'perp' or 'spot'
        entry_price = 0.0
        peak_price = 0.0
        spot_cost_basis = 0.0    # Cash tied up in spot inventory
        mmr = 0.025              # 2.5% Maintenance Margin Ratio for perp
        trades = []
        realized_pnl = 0.0
        total_fees = 0.0
        total_slippage_cost = 0.0
        funding_cashflows = 0.0
        
        log_returns = np.diff(np.log(perp_prices), prepend=np.log(perp_prices[0]))
        vol_window = 24
        
        for t in range(1, n_bars):
            curr_px = perp_prices[t]
            curr_spot_px = spot_prices[t]
            curr_funding = funding_rates[t]
            bar_vol = np.std(log_returns[max(0, t-vol_window):t]) + 0.001
            bar_vol_usd = volumes_usd[t]
            
            sig = signals[t-1]
            burst = burst_confs[t-1]
            
            # 1. Update position equity & trailing stop / profit checks
            unrealized_pnl = 0.0
            if position_size_coin != 0.0:
                if position_channel == 'perp':
                    unrealized_pnl = position_size_coin * (curr_px - entry_price)
                    # Check funding payment on perp positions (every 8 hours = 96 5m bars)
                    if t % 96 == 0:
                        funding_payment = - (position_size_coin * curr_px) * curr_funding
                        cash += funding_payment
                        funding_cashflows += funding_payment
                    current_equity = cash + unrealized_pnl
                    # Maintenance Margin Liquidation Check
                    pos_val = abs(position_size_coin) * curr_px
                    if current_equity < pos_val * mmr:
                        # Forced Liquidation
                        liq_slip = 0.005 # 50 bps liquidation penalty
                        liq_px = curr_px * (1.0 - liq_slip if position_size_coin > 0 else 1.0 + liq_slip)
                        realized = position_size_coin * (liq_px - entry_price)
                        cash += realized - (pos_val * self.perp_taker_fee)
                        cash = max(0.0, cash)
                        trades.append({
                            'pnl': realized - (pos_val * self.perp_taker_fee),
                            'return_pct': (liq_px - entry_price) / entry_price * np.sign(position_size_coin),
                            'channel': 'perp',
                            'reason': 'forced_liquidation_mmr'
                        })
                        position_size_coin = 0.0
                        position_channel = None
                        entry_price = 0.0
                        peak_price = 0.0
                        unrealized_pnl = 0.0
                else:
                    # Spot channel: total equity = remaining liquid cash + spot coin market value
                    spot_market_val = position_size_coin * curr_spot_px
                    unrealized_pnl = spot_market_val - spot_cost_basis
                    current_equity = cash + spot_market_val

            if position_size_coin != 0.0:
                # High-water mark tracking for trailing stop
                check_px = curr_px if position_channel == 'perp' else curr_spot_px
                if position_size_coin > 0:
                    peak_price = max(peak_price, check_px)
                    dd_from_peak = (peak_price - check_px) / entry_price
                    loss_from_entry = (entry_price - check_px) / entry_price
                else:
                    peak_price = min(peak_price, check_px)
                    dd_from_peak = (check_px - peak_price) / entry_price
                    loss_from_entry = (check_px - entry_price) / entry_price
                    
                # Exit logic
                must_exit = False
                exit_reason = None
                
                if loss_from_entry >= self.stop_loss_pct:
                    must_exit = True
                    exit_reason = "stop_loss"
                elif dd_from_peak >= self.take_profit_trailing_pct and ((check_px - entry_price) * np.sign(position_size_coin) > 0.015):
                    must_exit = True
                    exit_reason = "take_profit_trailing"
                elif np.sign(sig) != np.sign(position_size_coin) and abs(sig) > 0.35:
                    must_exit = True
                    exit_reason = "signal_reversal"
                elif burst < 0.25 and abs(sig) < 0.15:
                    must_exit = True
                    exit_reason = "momentum_exhaustion"
                    
                if must_exit:
                    order_val = abs(position_size_coin) * check_px
                    slip = self.calculate_market_impact_slippage(order_val, bar_vol_usd, bar_vol)
                    fee_rate = self.perp_taker_fee if position_channel == 'perp' else self.spot_taker_fee
                    
                    exit_px = check_px * (1.0 - slip if position_size_coin > 0 else 1.0 + slip)
                    trade_fee = order_val * fee_rate
                    trade_slip_cost = order_val * slip
                    
                    if position_channel == 'perp':
                        trade_pnl = position_size_coin * (exit_px - entry_price)
                        cash += trade_pnl - trade_fee
                    else:
                        # Spot exit: cash is credited with coin proceeds minus fee
                        proceeds = position_size_coin * exit_px
                        cash += proceeds - trade_fee
                        trade_pnl = proceeds - spot_cost_basis
                        spot_cost_basis = 0.0
                        
                    total_fees += trade_fee
                    total_slippage_cost += trade_slip_cost
                    trades.append({
                        'pnl': trade_pnl - trade_fee,
                        'return_pct': (exit_px - entry_price) / entry_price * np.sign(position_size_coin),
                        'channel': position_channel,
                        'reason': exit_reason
                    })
                    
                    position_size_coin = 0.0
                    position_channel = None
                    entry_price = 0.0
                    peak_price = 0.0
                    unrealized_pnl = 0.0
            # 2. Entry logic
            if position_size_coin == 0.0 and abs(sig) > self.entry_threshold and burst > self.burst_threshold:
                direction = np.sign(sig)
                
                # Intelligent Channel Routing:
                # Long + positive basis + high positive funding => spot preferred to avoid funding bleed
                # Short or explosive squeeze => perp channel for leverage & short capability
                if direction > 0 and curr_funding > 0.0006:
                    target_channel = 'spot'
                else:
                    target_channel = 'perp'
                    
                # Leverage & Channel Sizing
                slip = self.calculate_market_impact_slippage(self.initial_capital_usd, bar_vol_usd, bar_vol)
                fee_rate = self.perp_taker_fee if target_channel == 'perp' else self.spot_taker_fee
                entry_px = (curr_px if target_channel == 'perp' else curr_spot_px) * (1.0 + slip if direction > 0 else 1.0 - slip)
                
                if target_channel == 'spot':
                    # Spot cannot use leverage: order_usd cannot exceed available liquid cash
                    order_usd = min(cash * 0.95, self.initial_capital_usd)
                    if order_usd > 5000.0:
                        trade_fee = order_usd * fee_rate
                        cash -= (order_usd + trade_fee)
                        position_size_coin = order_usd / entry_px
                        spot_cost_basis = order_usd
                        position_channel = 'spot'
                        entry_price = entry_px
                        peak_price = entry_px
                        total_fees += trade_fee
                        total_slippage_cost += order_usd * slip
                else:
                    # Perp channel with leverage target
                    leverage_target = min(self.max_leverage, (abs(sig) * self.leverage_scale) * (0.02 / (bar_vol * np.sqrt(288) + 1e-4)))
                    order_usd = min(cash * leverage_target, self.initial_capital_usd * self.max_leverage)
                    if order_usd > 5000.0 and cash > (order_usd * mmr * 2.0):
                        trade_fee = order_usd * fee_rate
                        cash -= trade_fee
                        position_size_coin = (order_usd / entry_px) * direction
                        position_channel = 'perp'
                        entry_price = entry_px
                        peak_price = entry_px
                        total_fees += trade_fee
                        total_slippage_cost += order_usd * slip

            # Current total equity
            if position_size_coin != 0.0:
                if position_channel == 'perp':
                    equity_curve[t] = cash + position_size_coin * (curr_px - entry_price)
                else:
                    equity_curve[t] = cash + position_size_coin * curr_spot_px
            else:
                equity_curve[t] = cash
        # 3. Comprehensive Performance Metrics
        returns = np.diff(equity_curve) / equity_curve[:-1]
        returns = returns[np.isfinite(returns)]
        
        years = n_bars / self.bars_per_year
        total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]
        cagr = ((1.0 + max(-0.99, total_return)) ** (1.0 / max(years, 0.01)) - 1.0) * 100.0
        
        mean_ret = np.mean(returns)
        std_ret = np.std(returns) + 1e-9
        sharpe = (mean_ret / std_ret) * np.sqrt(self.bars_per_year)
        
        # Drawdowns
        running_max = np.maximum.accumulate(equity_curve)
        drawdowns = (running_max - equity_curve) / running_max
        max_drawdown = np.max(drawdowns) * 100.0
        calmar = cagr / (max_drawdown + 1e-5)
        
        win_trades = [tr for tr in trades if tr['pnl'] > 0]
        loss_trades = [tr for tr in trades if tr['pnl'] <= 0]
        win_rate = (len(win_trades) / len(trades) * 100.0) if trades else 0.0
        
        gross_profit = sum(tr['pnl'] for tr in win_trades)
        gross_loss = abs(sum(tr['pnl'] for tr in loss_trades)) + 1e-8
        profit_factor = gross_profit / gross_loss
        
        return {
            'cagr': cagr,
            'sharpe': sharpe,
            'max_drawdown': max_drawdown,
            'calmar': calmar,
            'win_rate': win_rate,
            'total_trades': len(trades),
            'profit_factor': profit_factor,
            'final_equity_cny': equity_curve[-1] * self.cny_usd_rate,
            'total_fees_cny': total_fees * self.cny_usd_rate,
            'slippage_cost_cny': total_slippage_cost * self.cny_usd_rate,
            'funding_pnl_cny': funding_cashflows * self.cny_usd_rate,
            'equity_curve': equity_curve
        }
