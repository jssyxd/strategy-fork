#!/usr/bin/env bash
set -e

# Autoresearch Benchmark Execution Harness
docker compose run --rm -e PYTHONUNBUFFERED=1 nautilus python benchmark_harness.py
