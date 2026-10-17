FROM python:3.11-slim

LABEL maintainer="Quantitative Research - Jane Street Style"
LABEL description="Nautilus Trader Backtest Engine Container"

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
    scipy \
    matplotlib

COPY . /app

CMD ["python", "run_docker_backtest.py"]
