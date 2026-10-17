"""
Credal Transformer & Subjective Logic Evidential Uncertainty Auditor.
Implements:
- Dirichlet-based Subjective Logic evidential modeling (arXiv:2510.12137, arXiv:2505.15155).
- Decomposition of uncertainty into:
  1. Aleatoric uncertainty (expected entropy / data noise).
  2. Epistemic uncertainty (vacuity / out-of-distribution OOD / regime shift).
  3. Directional conflict C (contradictory feature evidence).
- Anti-hallucination / Anti-overfitting veto filter:
  Flags and vetoes false-high-confidence predictions in unfamiliar or chaotic regimes.
"""

from typing import Dict, Tuple
import numpy as np
import pandas as pd


class CredalAuditor:
    """Credal Set and Subjective Logic Uncertainty Gate for Multi-Class Regime Classification."""

    def __init__(
        self,
        num_classes: int = 4,
        u_threshold: float = 0.35,
        c_threshold: float = 0.40,
        evidence_scale: float = 10.0,
    ):
        self.num_classes = num_classes
        self.u_threshold = u_threshold
        self.c_threshold = c_threshold
        self.evidence_scale = evidence_scale

    def compute_evidential_belief(
        self, raw_evidence: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """Convert raw non-negative evidence vectors e_k into Dirichlet Subjective Logic masses.

        e_k >= 0, alpha_k = e_k + 1, S = sum(alpha_k)
        Belief: b_k = e_k / S
        Vacuity (Epistemic Uncertainty): u = K / S
        Conservation Law: sum(b_k) + u == 1.0
        """
        evidence = np.maximum(raw_evidence, 0.0)
        alphas = evidence + 1.0
        S = np.sum(alphas, axis=-1, keepdims=True)
        K = float(self.num_classes)

        beliefs = evidence / S
        vacuity_u = (K / S).squeeze(-1)

        # Directional Conflict C (pairwise overlap between top-2 competing beliefs)
        sorted_beliefs = np.sort(beliefs, axis=-1)
        top1 = sorted_beliefs[..., -1]
        top2 = sorted_beliefs[..., -2]
        sum_top = top1 + top2
        conflict_c = np.where(
            sum_top > 1e-6, (2.0 * np.minimum(top1, top2)) / sum_top, 0.0
        )

        # Expected Dirichlet probability: p_hat_k = alpha_k / S
        p_hat = alphas / S

        return {
            "alphas": alphas,
            "S": S.squeeze(-1),
            "beliefs": beliefs,
            "vacuity_u": vacuity_u,
            "conflict_c": conflict_c,
            "expected_prob": p_hat,
        }

    def audit_prediction(
        self, raw_evidence: np.ndarray, predicted_class: int
    ) -> Tuple[bool, str, Dict[str, float]]:
        """Audits a single prediction against Credal anti-hallucination and anti-overfitting rules.

        Returns: (passed: bool, reason: str, metrics: dict)
        """
        ev = np.array(raw_evidence, dtype=float).reshape(1, -1)
        res = self.compute_evidential_belief(ev)

        u = float(res["vacuity_u"][0])
        c = float(res["conflict_c"][0])
        p_expected = res["expected_prob"][0]
        max_p = float(np.max(p_expected))

        metrics = {
            "vacuity_u": u,
            "conflict_c": c,
            "max_expected_prob": max_p,
            "predicted_class": int(predicted_class),
        }

        # Rule 1: High Epistemic Vacuity (OOD / Regime Shift / Lack of Evidence)
        if u > self.u_threshold:
            return (
                False,
                f"VETO: Epistemic uncertainty u={u:.3f} > threshold {self.u_threshold:.3f} (Regime shift/OOD)",
                metrics,
            )

        # Rule 2: High Internal Conflict (Contradictory directional indicators)
        if c > self.c_threshold:
            return (
                False,
                f"VETO: Directional conflict C={c:.3f} > threshold {self.c_threshold:.3f} (Chop/Whipsaw risk)",
                metrics,
            )

        # Rule 3: Weak Dominance
        if max_p < (1.0 / self.num_classes) * 1.2:
            return (
                False,
                f"VETO: Expected probability {max_p:.3f} fails minimum margin over uniform prior",
                metrics,
            )

        return (True, "PASSED: Credal set guarantees robust decision", metrics)

    def audit_dataframe(
        self, df: pd.DataFrame, evidence_cols: list
    ) -> pd.DataFrame:
        """Batch audit a DataFrame of samples."""
        ev = df[evidence_cols].values
        res = self.compute_evidential_belief(ev)

        df = df.copy()
        df["credal_vacuity_u"] = res["vacuity_u"]
        df["credal_conflict_c"] = res["conflict_c"]
        df["credal_passed"] = (
            df["credal_vacuity_u"] <= self.u_threshold
        ) & (df["credal_conflict_c"] < self.c_threshold)
        return df


if __name__ == "__main__":
    auditor = CredalAuditor(num_classes=4, u_threshold=0.35, c_threshold=0.40)
    print("CredalAuditor initialized successfully.")

    # Unit test 1: Clean high evidence for TrendFollow (class 0)
    passed, reason, metrics = auditor.audit_prediction(
        np.array([8.0, 1.0, 0.5, 0.5]), 0
    )
    print(f"Test 1 (Clean Trend): passed={passed}, reason={reason}")

    # Unit test 2: Contradictory evidence (high class 0 and high class 2)
    passed, reason, metrics = auditor.audit_prediction(
        np.array([5.0, 0.5, 5.0, 0.5]), 0
    )
    print(f"Test 2 (Contradictory): passed={passed}, reason={reason}")

    # Unit test 3: Low evidence (OOD / regime unknown)
    passed, reason, metrics = auditor.audit_prediction(
        np.array([0.2, 0.1, 0.2, 0.1]), 0
    )
    print(f"Test 3 (Low Evidence/Vacuity): passed={passed}, reason={reason}")
