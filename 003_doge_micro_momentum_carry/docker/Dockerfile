FROM python:3.11-slim

LABEL maintainer="Quantitative Research - Jane Street Style"
LABEL description="003 DOGE Microstructure Momentum & Carry Strategy Backtest Engine Container"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install NautilusTrader and high-performance quantitative stack
RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com \
    nautilus_trader==1.221.0 \
    pandas \
    numpy \
    pyarrow \
    scipy

COPY . /app

CMD ["python", "src/run_nautilus_backtest.py", "binance_real"]
