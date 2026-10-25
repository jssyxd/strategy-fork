# Dockerfile for NautilusTrader Strategy Service 04_nd100_enh
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends     build-essential curl ca-certificates &&     rm -rf /var/lib/apt/lists/*

# Install python dependencies
RUN pip install --no-cache-dir     numpy pandas scipy lightgbm requests pyarrow

# Copy cluster files
COPY gateway_okx_client.py /app/gateway_okx_client.py
COPY config/ /app/config/
COPY services/04_nd100_enh/run_live.py /app/run_live.py

CMD ["python", "-u", "/app/run_live.py"]
