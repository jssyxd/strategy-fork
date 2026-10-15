"""
Deterministic Microstructure Market Generator for DOGEUSDT Perpetual & Spot.
Simulates realistic limit order book, taker flows, funding dynamics, and liquidation cascades.
"""

import numpy as np

def generate_doge_microstructure_dataset(n_bars=35000, seed=20261014):
    """
    Generates synthetic realistic high-frequency DOGE microstructure time series.
    n_bars: 35000 bars (~4 months of 5-minute bars)
    """
    rng = np.random.RandomState(seed)
    
    # 1. Base price dynamics: Jump-diffusion with regime-switching volatility
    base_price = 0.1250 # Starting DOGE price ~ $0.125
    daily_vol = 0.065   # DOGE 6.5% daily vol
    bar_vol = daily_vol / np.sqrt(288)
    
    # Generate volatility regimes (calm vs retail meme mania)
    vol_regime = np.ones(n_bars)
    regime = 1.0
    for t in range(1, n_bars):
        if rng.rand() < 0.008:
            regime = 2.8 if regime < 1.5 else 0.8
        vol_regime[t] = regime
        
    local_sigma = bar_vol * vol_regime
    innovations = rng.standard_t(df=4.0, size=n_bars) * local_sigma
    
    # Add jump bursts (retail meme momentum & liquidation spikes)
    jumps = np.zeros(n_bars)
    jump_indices = rng.choice(n_bars, size=int(n_bars * 0.015), replace=False)
    jumps[jump_indices] = rng.choice([-1, 1], size=len(jump_indices)) * rng.uniform(0.012, 0.038, size=len(jump_indices))
    
    log_returns = innovations + jumps
    log_prices = np.log(base_price) + np.cumsum(log_returns)
    perp_close = np.exp(log_prices)
    
    # High-Low-Open
    high_mult = 1.0 + np.abs(rng.randn(n_bars)) * local_sigma * 1.5
    low_mult = 1.0 - np.abs(rng.randn(n_bars)) * local_sigma * 1.5
    perp_high = np.maximum(perp_close * high_mult, perp_close)
    perp_low = np.minimum(perp_close * low_mult, perp_close)
    perp_open = np.roll(perp_close, 1)
    perp_open[0] = perp_close[0]
    
    # 2. Volume & Taker Flow (CVD)
    base_vol_usd = 450000.0 # ~450k USD per 5m bar (~130M USD/day)
    vol_multiplier = np.exp(np.abs(log_returns) / (bar_vol + 1e-5) * 0.4) * (vol_regime ** 1.2)
    volume_usd = base_vol_usd * vol_multiplier * rng.lognormal(0, 0.35, n_bars)
    volume_coins = volume_usd / perp_close
    
    # Taker buy / sell split based strictly on contemporaneous return and lagged momentum (strictly causal)
    lag_ret = np.roll(log_returns, 1)
    lag_ret[0] = 0.0
    buy_ratio = 0.50 + 0.35 * np.tanh(log_returns / local_sigma) + 0.10 * np.tanh(lag_ret / local_sigma) + rng.randn(n_bars) * 0.06
    buy_ratio = np.clip(buy_ratio, 0.15, 0.85)
    
    taker_buy_vol = volume_coins * buy_ratio
    taker_sell_vol = volume_coins * (1.0 - buy_ratio)
    # 3. Order Book Depth (5 levels bid/ask)
    depth_levels = 5
    spread_bps = 0.0003 + 0.0008 * (vol_regime - 1.0) # 3 bps to 15 bps
    spread_half = perp_close * (spread_bps / 2.0)
    
    bid_prices = np.zeros((n_bars, depth_levels))
    ask_prices = np.zeros((n_bars, depth_levels))
    bid_sizes = np.zeros((n_bars, depth_levels))
    ask_sizes = np.zeros((n_bars, depth_levels))
    
    for lvl in range(depth_levels):
        step_offset = perp_close * (spread_bps * (lvl + 0.5))
        bid_prices[:, lvl] = perp_close - spread_half - step_offset
        ask_prices[:, lvl] = perp_close + spread_half + step_offset
        
        # Order Book Imbalance driven by past volume delta and contemporaneous momentum (strictly causal)
        base_queue = (volume_coins / 10.0) * (1.2 ** lvl)
        bid_skew = np.clip(0.5 + 0.30 * np.tanh(log_returns / local_sigma) + rng.randn(n_bars) * 0.10, 0.1, 0.9)
        bid_sizes[:, lvl] = base_queue * (bid_skew * 2.0)
        ask_sizes[:, lvl] = base_queue * ((1.0 - bid_skew) * 2.0)
    # 4. Spot Price & Basis
    # Perp trades at a premium during bull runs and discount during panic
    basis_spread_ratio = 0.0008 * np.tanh(np.convolve(log_returns, np.ones(12)/12, mode='same') / bar_vol) + rng.randn(n_bars) * 0.0002
    spot_close = perp_close * (1.0 - basis_spread_ratio)
    
    # 5. Funding Rates (every 8h settled, continuous proxy)
    # Surges when basis is high
    funding_rate = 0.0001 + 0.0012 * basis_spread_ratio + rng.randn(n_bars) * 0.00005
    funding_rate = np.clip(funding_rate, -0.002, 0.0035)
    
    # 6. Liquidations
    # Short squeeze occurs on upside breakout; long liquidation cascade on sharp drop
    long_liq = np.maximum(0, -log_returns / local_sigma - 1.5) ** 2 * 65000.0 * rng.uniform(0.5, 2.0, n_bars)
    short_liq = np.maximum(0, log_returns / local_sigma - 1.5) ** 2 * 65000.0 * rng.uniform(0.5, 2.0, n_bars)
    
    return {
        'perp_open': perp_open,
        'perp_high': perp_high,
        'perp_low': perp_low,
        'perp_close': perp_close,
        'spot_close': spot_close,
        'volume': volume_coins,
        'taker_buy_vol': taker_buy_vol,
        'taker_sell_vol': taker_sell_vol,
        'bid_prices': bid_prices,
        'ask_prices': ask_prices,
        'bid_sizes': bid_sizes,
        'ask_sizes': ask_sizes,
        'funding_rate': funding_rate,
        'long_liquidation': long_liq,
        'short_liquidation': short_liq
    }
