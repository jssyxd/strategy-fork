# softbox.py – backtest statistics generation (OCR extracted)

import matplotlib.pyplot as plt

# Example backtest plot (simplified, actual data not captured)
plt.figure(figsize=(12, 6))
# Placeholder data
x = range(100)
plt.plot(x, x, label='Cum_Strategy', color='darkred', linewidth=2)
plt.plot(x, [i*0.9 for i in x], label='Cum_Benchmark', color='gray', alpha=0.7)
plt.title('Backtest: Nasdaq ETF vs AI Strategy')
plt.ylabel('Cumulative Return')
plt.legend(loc='upper left')
plt.tight_layout()
plt.show()
