import json, os, datetime, urllib.request
from decimal import Decimal

from nautilus_trader.model import (InstrumentId, Currency, Price, Quantity, Bar, BarType,
    BarSpecification, BarAggregation, PriceType, AggregationSource, CryptoPerpetual, Symbol)
from nautilus_trader.persistence import ParquetDataCatalog

DATA = "/root/bt013/data"
CAT = "/root/bt013/catalog"
SYMBOLS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]
SPECS = {"15m": (15, BarAggregation.MINUTE), "1h": (1, BarAggregation.HOUR),
         "4h": (4, BarAggregation.HOUR), "1d": (1, BarAggregation.DAY)}
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

def log(*a):
    print("CAT|", *a, flush=True)

def fetch_instruments():
    path = os.path.join(DATA, "instruments_swap.json")
    if not os.path.exists(path):
        req = urllib.request.Request("https://www.okx.com/api/v5/public/instruments?instType=SWAP", headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read().decode())
        if payload.get("code") != "0":
            raise RuntimeError("okx instruments error: %s" % payload.get("msg"))
        with open(path, "w") as f:
            json.dump(payload["data"], f)
        log("fetched instruments:", len(payload["data"]))
    with open(path) as f:
        rows = json.load(f)
    return {r["instId"]: r for r in rows}

def decimals(s):
    s = str(s)
    if "." in s:
        return len(s.split(".")[1].rstrip("0")) if s.split(".")[1].rstrip("0") else 0
    return 0

def build_instrument(row):
    prec_p = decimals(row["tickSz"])
    prec_s = decimals(row["lotSz"])
    return CryptoPerpetual(
        instrument_id=InstrumentId.from_str(row["instId"] + ".OKX"),
        raw_symbol=Symbol.from_str(row["instId"]),
        base_currency=Currency.from_str(row["ctValCcy"]),
        quote_currency=Currency.from_str(row["settleCcy"]),
        settlement_currency=Currency.from_str(row["settleCcy"]),
        is_inverse=False,
        price_precision=prec_p, size_precision=prec_s,
        price_increment=Price.from_str(row["tickSz"]),
        size_increment=Quantity.from_str(row["lotSz"]),
        ts_event=0, ts_init=0,
        multiplier=Quantity.from_str(row["ctVal"]),
        min_quantity=Quantity.from_str(row["minSz"]) if row.get("minSz") else None,
        margin_init=Decimal("0.05"), margin_maint=Decimal("0.005"))

def load_bars(sym, label, price_prec, size_prec):
    spec = BarSpecification(SPECS[label][0], SPECS[label][1], PriceType.LAST)
    bt = BarType(InstrumentId.from_str(sym + ".OKX"), spec, AggregationSource.EXTERNAL)
    out = []
    skipped_unconfirmed = 0
    with open(os.path.join(DATA, "%s_%s.jsonl" % (sym, label))) as f:
        for line in f:
            r = json.loads(line)
            if len(r) > 8 and r[8] != "1":
                skipped_unconfirmed += 1
                continue
            ts = int(r[0]) * 1_000_000
            vol = ("%%.%df" % size_prec) % float(r[5])
            pf = "%%.%df" % price_prec
            out.append(Bar(bt, Price.from_str(pf % float(r[1])), Price.from_str(pf % float(r[2])),
                           Price.from_str(pf % float(r[3])), Price.from_str(pf % float(r[4])),
                           Quantity.from_str(vol), ts, ts))
    return out, skipped_unconfirmed

def main():
    os.makedirs(CAT, exist_ok=True)
    inst_map = fetch_instruments()
    catalog = ParquetDataCatalog(CAT)
    instruments = []
    for sym in SYMBOLS:
        row = inst_map.get(sym)
        if row is None:
            raise RuntimeError("missing instrument " + sym)
        instr = build_instrument(row)
        instruments.append(instr)
        log("%s: tick=%s lot=%s ctVal=%s(%s) minSz=%s prec=(%d,%d)" % (
            sym, row["tickSz"], row["lotSz"], row["ctVal"], row["ctValCcy"], row["minSz"],
            instr.price_precision, instr.size_precision))
    catalog.write_instruments(instruments)
    log("instruments written")
    total = 0
    prec_by_sym = {i.id.value.split(".")[0]: i.price_precision for i in instruments}
    size_by_sym = {i.id.value.split(".")[0]: i.size_precision for i in instruments}
    for sym in SYMBOLS:
        for label in SPECS:
            bars, skipped = load_bars(sym, label, prec_by_sym[sym], size_by_sym[sym])
            if bars:
                catalog.write_bars(bars, skip_disjoint_check=True)
            total += len(bars)
            log("%s %s: %d bars written (skipped unconfirmed=%d), span %s .. %s" % (
                sym, label, len(bars), skipped,
                datetime.datetime.utcfromtimestamp(bars[0].ts_event / 1_000_000_000).strftime("%Y-%m-%d") if bars else "-",
                datetime.datetime.utcfromtimestamp(bars[-1].ts_event / 1_000_000_000).strftime("%Y-%m-%d") if bars else "-"))
            del bars
    log("DONE bars=%d" % total)

main()
