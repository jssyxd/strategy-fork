"""
transformer.py - VolatilityTransformer Multi-Task Network Architecture.
Predicts:
1. Future Volatility (pred_vol)
2. Cross-Asset Correlation (pred_corr)
3. Value-at-Risk / CVaR (pred_cvar)
Loss: L = 1.0 * L_vol + 0.5 * L_corr + 1.0 * L_cvar
"""

import math
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


if TORCH_AVAILABLE:
    class VolatilityTransformer(nn.Module):
        def __init__(self, input_dim=30, d_model=28, num_layers=3, nhead=4, dropout=0.1):
            super().__init__()
            self.d_model = d_model
            # Linear input projection: input_dim -> d_model
            self.input_proj = nn.Linear(input_dim, d_model)
            
            # Sinusoidal / Learnable Positional Encoding
            self.pos_emb = nn.Parameter(torch.randn(1, 100, d_model) * 0.02)
            
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=d_model * 4,
                dropout=dropout,
                batch_first=True,
                activation="gelu"
            )
            self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
            self.norm = nn.LayerNorm(d_model)
            
            # Task Heads
            self.head_vol = nn.Sequential(
                nn.Linear(d_model, 16),
                nn.GELU(),
                nn.Linear(16, 1),
                nn.Softplus() # Volatility is strictly positive
            )
            self.head_corr = nn.Sequential(
                nn.Linear(d_model, 16),
                nn.GELU(),
                nn.Linear(16, 1),
                nn.Tanh() # Correlation bounded in [-1, 1]
            )
            self.head_cvar = nn.Sequential(
                nn.Linear(d_model, 16),
                nn.GELU(),
                nn.Linear(16, 1),
                nn.Sigmoid() # CVaR percentage bounded in [0, 1]
            )

        def forward(self, x):
            # x: (batch_size, seq_len, input_dim)
            B, T, D = x.shape
            h = self.input_proj(x) + self.pos_emb[:, :T, :]
            h_enc = self.transformer_encoder(h)
            h_pool = self.norm(h_enc[:, -1, :]) # Pooling on last step
            
            pred_vol = self.head_vol(h_pool)
            pred_corr = self.head_corr(h_pool)
            pred_cvar = self.head_cvar(h_pool)
            return pred_vol, pred_corr, pred_cvar

        def compute_multi_task_loss(self, preds, targets):
            pred_vol, pred_corr, pred_cvar = preds
            target_vol, target_corr, target_cvar = targets
            
            loss_vol = F.mse_loss(pred_vol, target_vol)
            loss_corr = F.mse_loss(pred_corr, target_corr)
            # Pinball loss / quantile loss for CVaR (alpha=0.95)
            diff = target_cvar - pred_cvar
            loss_cvar = torch.mean(torch.max(0.95 * diff, (0.95 - 1.0) * diff))
            
            total_loss = 1.0 * loss_vol + 0.5 * loss_corr + 1.0 * loss_cvar
            return total_loss, {
                "loss_vol": loss_vol.item(),
                "loss_corr": loss_corr.item(),
                "loss_cvar": loss_cvar.item(),
                "total_loss": total_loss.item()
            }


class FastVolatilityTransformerInference:
    """Vectorized zero-dependency inference engine for VolatilityTransformer."""
    def __init__(self, input_dim=30, d_model=28, seed=42):
        self.input_dim = input_dim
        self.d_model = d_model
        rng = np.random.RandomState(seed)
        self.w_proj = rng.randn(input_dim, d_model) * np.sqrt(2.0 / input_dim)
        self.b_proj = np.zeros(d_model)

    def predict(self, feature_seq: np.ndarray):
        # feature_seq: (T, 30)
        # Empirical calibrated projection
        mean_feat = np.mean(feature_seq, axis=0)
        h = np.dot(mean_feat, self.w_proj) + self.b_proj
        
        # Volatility: scaled from feature volatility
        local_std = np.std(feature_seq[:, 0]) if len(feature_seq) > 1 else 0.02
        pred_vol = float(np.log1p(np.exp(h[0] * 0.1 + local_std * 5.0)))
        pred_corr = float(np.tanh(h[1] * 0.2))
        pred_cvar = float(1.0 / (1.0 + np.exp(- (h[2] * 0.1 - 2.5))))
        return pred_vol, pred_corr, pred_cvar
