#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NautilusTrader 官方事件驱动引擎原生运行脚本
适配 006 ETH AI AlphaEvolve Q-Learning 策略
"""

import os
import sys
from decimal import Decimal
import pandas as pd
import numpy as np

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import BarAggregation, PriceType, OmsType, AccountType, OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue, TraderId
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Price, Quantity, Money, Currency
from nautilus_trader.execution.models import FeeModel
from nautilus_trader.trading.strategy import Strategy

print("NautilusTrader modules imported successfully.")
