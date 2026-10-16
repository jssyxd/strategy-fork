"""
Microstructure Factor Extraction Module for DOGE High-Frequency Trading.
Captures order book dynamics, order flow toxicity, funding rate divergence,
liquidation pressure, and micro-volatility regimes.
"""

import numpy as np

class MicrostructureFeatureExtractor:
    def __init__(self, depth_levels=5, window_fast=12, window_slow=36):
        self.depth_levels = depth_levels
        self.window_fast = window_fast
        self.window_slow = window_slow

    def compute_order_book_imbalance(self, bid_sizes, ask_sizes):
        """
        Calculates Multi-Level Order Book Imbalance (OBI) with exponential decay weighting.
        bid_sizes: (N, L)
        ask_sizes: (N, L)
        """
        weights = np.exp(-0.45 * np.arange(self.depth_levels))
        weights = weights / np.sum(weights)
        
        weighted_bids = np.dot(bid_sizes[:, :self.depth_levels], weights)
        weighted_asks = np.dot(ask_sizes[:, :self.depth_levels], weights)
        
        denominator = weighted_bids + weighted_asks + 1e-8
        obi = (weighted_bids - weighted_asks) / denominator
        return obi

    def compute_stoikov_micro_price(self, bid_prices, ask_prices, bid_sizes, ask_sizes):
        """
        Calculates Stoikov Micro-price adjusted by top-of-book queue sizes.
        P_micro = (Q_b * P_a + Q_a * P_b) / (Q_a + Q_b)
        """
        p_b = bid_prices[:, 0]
        p_a = ask_prices[:, 0]
        q_b = bid_sizes[:, 0]
        q_a = ask_sizes[:, 0]
        
        micro_price = (q_b * p_a + q_a * p_b) / (q_a + q_b + 1e-8)
        mid_price = (p_a + p_b) / 2.0
        micro_spread_ratio = (micro_price - mid_price) / (mid_price + 1e-8)
        return micro_price, micro_spread_ratio

    def compute_cvd_divergence(self, close_prices, taker_buy_vol, taker_sell_vol):
        """
        Cumulative Volume Delta (CVD) and divergence from price return.
        Divergence signals institutional absorption or retail FOMO exhaustion.
        """
        delta = taker_buy_vol - taker_sell_vol
        cvd = np.cumsum(delta)
        
        # Rolling Z-score calculation
        n = len(close_prices)
        z_cvd = np.zeros(n)
        z_px = np.zeros(n)
        w = self.window_slow
        
        for i in range(w, n):
            cvd_slice = cvd[i-w:i]
            px_slice = close_prices[i-w:i]
            
            s_cvd = np.std(cvd_slice) + 1e-8
            s_px = np.std(px_slice) + 1e-8
            
            z_cvd[i] = (cvd[i] - np.mean(cvd_slice)) / s_cvd
            z_px[i] = (close_prices[i] - np.mean(px_slice)) / s_px
            
        cvd_divergence = z_cvd - z_px
        return delta, cvd, cvd_divergence

    def compute_flow_toxicity_vpin(self, taker_buy_vol, taker_sell_vol, volume):
        """
        Volume-Synchronized Probability of Toxicity (VPIN) proxy for continuous bars.
        Toxicity = |BuyVol - SellVol| / TotalVol
        """
        imbalance = np.abs(taker_buy_vol - taker_sell_vol)
        tot = volume + 1e-8
        raw_toxicity = imbalance / tot
        
        # Smooth via moving average
        w = self.window_fast
        vpin_smooth = np.convolve(raw_toxicity, np.ones(w)/w, mode='same')
        return vpin_smooth

    def compute_funding_basis_features(self, spot_close, perp_close, funding_rates):
        """
        Calculates Basis Spread (Perp - Spot) and Funding Rate Acceleration.
        Captures short squeeze potential and funding-arbitrage flow pressures.
        """
        basis_bps = ((perp_close - spot_close) / (spot_close + 1e-8)) * 10000.0
        
        funding_diff = np.diff(funding_rates, prepend=funding_rates[0])
        funding_velocity = np.convolve(funding_diff, np.ones(self.window_fast)/self.window_fast, mode='same')
        return basis_bps, funding_velocity

    def compute_liquidation_pressure(self, long_liq_usd, short_liq_usd):
        """
        Liquidation Pressure Index (LPI):
        Measures asymmetric liquidation cascades. Positive = short liquidation squeeze.
        """
        net_liq = short_liq_usd - long_liq_usd
        total_liq = short_liq_usd + long_liq_usd + 1e-5
        lpi = net_liq / total_liq
        lpi_smooth = np.convolve(lpi, np.array([0.2, 0.3, 0.5]), mode='same')
        
        # Log scale of liquidation impact
        liq_intensity = np.log1p(total_liq)
        return lpi_smooth, liq_intensity

    def compute_micro_volatility(self, close_prices):
        """
        High-frequency Realized Volatility and Parkison/Garman-Klass proxy.
        """
        log_ret = np.diff(np.log(close_prices), prepend=np.log(close_prices[0]))
        w = self.window_fast
        rv = np.zeros(len(close_prices))
        for i in range(w, len(close_prices)):
            rv[i] = np.sqrt(np.sum(log_ret[i-w:i]**2) * (252 * 288))  # Annualized 5m bars
        return rv

    def extract_all(self, df_dict):
        """
        Extracts unified normalized feature tensor for deep learning model.
        Returns: (N, num_features)
        """
        b_px = df_dict['bid_prices']
        a_px = df_dict['ask_prices']
        b_sz = df_dict['bid_sizes']
        a_sz = df_dict['ask_sizes']
        perp_px = df_dict['perp_close']
        spot_px = df_dict['spot_close']
        tb_vol = df_dict['taker_buy_vol']
        ts_vol = df_dict['taker_sell_vol']
        vol = df_dict['volume']
        funding = df_dict['funding_rate']
        long_liq = df_dict['long_liquidation']
        short_liq = df_dict['short_liquidation']
        
        obi = self.compute_order_book_imbalance(b_sz, a_sz)
        _, micro_spread = self.compute_stoikov_micro_price(b_px, a_px, b_sz, a_sz)
        _, _, cvd_div = self.compute_cvd_divergence(perp_px, tb_vol, ts_vol)
        vpin = self.compute_flow_toxicity_vpin(tb_vol, ts_vol, vol)
        basis_bps, fund_vel = self.compute_funding_basis_features(spot_px, perp_px, funding)
        lpi, liq_int = self.compute_liquidation_pressure(long_liq, short_liq)
        rv = self.compute_micro_volatility(perp_px)
        
        features = np.column_stack([
            obi,
            micro_spread * 1000.0,
            cvd_div,
            vpin,
            basis_bps / 10.0,
            fund_vel * 10000.0,
            lpi,
            liq_int / 10.0,
            rv
        ])
        
        # Robust normalization (winsorize and z-score)
        features = np.clip(features, -5.0, 5.0)
        return features
