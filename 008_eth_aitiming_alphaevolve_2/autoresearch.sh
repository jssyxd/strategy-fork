#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure venv exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv .venv
    source .venv/bin/activate
    uv pip install nautilus-trader vectorbt "plotly<6"
else
    source .venv/bin/activate
fi

# 1. Validate data lake integrity
python3 validate_data.py

# 2. Run NautilusTrader event-driven backtest
python3 nautilus_backtest_engine.py

# 3. Run VectorBT portfolio backtest
python3 vectorbt_backtest_engine.py

# 4. Run cross-engine comparison & reconciliation
python3 compare_engines.py

# 5. Render dual HTML reports & audit report
python3 render_reports.py

# 6. Parse metrics and emit canonical METRIC lines
python3 -c "
import json

with open('reports/dual_engine_comparison.json') as f:
    comp = json.load(f)
with open('reports/nautilus_metrics.json') as f:
    nt = json.load(f)

# Primary metric: match_rate (100.0% concordance between engines)
print(f'METRIC match_rate={comp[\"dual_engine_match_rate_pct\"]:.1f}')

# Secondary metrics
print(f'METRIC total_return_pct={nt[\"total_return_pct\"]:.2f}')
print(f'METRIC win_rate_pct={nt[\"win_rate_pct\"]:.2f}')
print(f'METRIC sharpe_ratio={nt[\"sharpe_ratio\"]:.2f}')
print(f'METRIC max_drawdown_pct={nt[\"max_drawdown_pct\"]:.2f}')
print(f'METRIC profit_factor={nt[\"profit_factor\"]:.3f}')
print(f'METRIC total_trades={nt[\"total_trades\"]}')
"

exit 0
