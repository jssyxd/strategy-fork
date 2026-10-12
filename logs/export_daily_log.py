#!/usr/bin/env python3
"""按北京时间自然日，从某个 smc-trader 实例的日志中切出某一天的日志。

用法:
    # 主实例（无 stream 后缀，文件名 smc_matrix_YYYY_MM_DD.log）
    python3 export_daily_log.py 2026-10-11 /tmp/live.log --old /tmp/live.log.old

    # 多实例（c1 / c2 ...，文件名 smc_matrix_c1_YYYY_MM_DD.log）
    python3 export_daily_log.py 2026-10-11 /tmp/live-c1.log --stream c1
    python3 export_daily_log.py 2026-10-11 /tmp/live-c2.log --stream c2

内容逐字节原样，不做任何加工。--old 只在主实例首次归档时需要（首个归档文件里混有
live.log.old 的内容，校验时要按它实际的字节数扣除偏移）。

归日规则
--------
同一文件内有两种时间戳：
  * 策略自身 logger  : "2026-10-11 12:22:05,015 [INFO]"      -> 已是北京时间
  * NautilusTrader  : "2026-10-11T04:22:05.000000000Z [INFO]" -> UTC，需 +8h
把每行按换算后的**北京日期**归入对应文件；续行（无时间戳）沿用上一行的日期归属。
因此次日导出天然从 00:00:00 续接，不重不漏。

自校验
------
1. 连续性：**同一 stream** 已归档的各日文件按日期顺序拼接后，应当等于当前日志的一个前缀。
   首个归档文件里混有 live.log.old 的内容，按 --old 指定文件的实际字节数扣除。
   该 stream 尚无归档（例如新上的实例）时跳过本项。
2. 零丢失：把整个源日志按日期分桶后再拼回去，必须与原文逐字节相同。
任一校验失败即退出码 1，不写出任何文件。
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from datetime import datetime, timedelta

ANSI = re.compile(rb"\x1b\[[0-9;]*m")
LOC = re.compile(r"^(\d{4}-\d{2}-\d{2}) \d{2}:")
UTC = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}):")
# smc_matrix_2026_10_11.log -> stream=None(main) ; smc_matrix_c1_2026_10_11.log -> stream="c1"
NAME = re.compile(r"^smc_matrix(?:_([a-z][a-z0-9]*))?_(\d{4})_(\d{2})_(\d{2})\.log$")


def cst_day(line: bytes) -> str | None:
    """返回该行的北京日期 (YYYY-MM-DD)；无时间戳的续行返回 None。"""
    s = ANSI.sub(b"", line).decode("utf-8", "replace")
    if m := LOC.match(s):
        return m.group(1)
    if m := UTC.match(s):
        shifted = datetime.strptime(f"{m.group(1)}T{m.group(2)}", "%Y-%m-%dT%H") + timedelta(hours=8)
        return shifted.strftime("%Y-%m-%d")
    return None


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def parse_args(argv: list[str]):
    """位置参数: <date> <src>；可选: --stream NAME  --old PATH"""
    pos, stream, old = [], "main", None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--stream":
            i += 1
            stream = argv[i]
        elif a == "--old":
            i += 1
            old = argv[i]
        elif a.startswith("--"):
            raise SystemExit(f"未知参数: {a}")
        else:
            pos.append(a)
        i += 1
    if len(pos) < 2:
        raise SystemExit(__doc__)
    return pos[0], pos[1], stream, old


def main() -> int:
    day, src, stream, old = parse_args(sys.argv[1:])
    out_dir = os.path.dirname(os.path.abspath(__file__))
    suffix = "" if stream in ("main", "", None) else f"_{stream}"

    raw = open(src, "rb").read()
    print(f"源日志 : {src}  ({len(raw):,} 字节)")
    print(f"实例   : {stream}")
    print(f"目标日 : {day} (北京时间)")

    # ── 自校验 1：与**同一 stream** 已归档的日期连续 ──────────────
    archived = []
    for name in sorted(os.listdir(out_dir)):
        if m := NAME.match(name):
            s = m.group(1) or "main"
            if s == stream:
                archived.append((f"{m.group(2)}-{m.group(3)}-{m.group(4)}", os.path.join(out_dir, name)))
    if archived:
        k = os.path.getsize(old) if old and os.path.exists(old) else 0
        blob = b"".join(open(p, "rb").read() for _, p in archived)
        expected = blob[k:] if k else blob
        ok = raw[: len(expected)] == expected
        print(f"连续性 : {stream} 已归档 {len(archived)} 天，扣除旧段 {k:,} 字节后与当前日志前缀比对 -> "
              f"{'OK' if ok else 'FAIL'}")
        if not ok:
            print("!! 归档与当前日志不连续（可能发生轮转或截断），已中止。")
            return 1
    else:
        print(f"连续性 : {stream} 尚无归档，跳过（首次归档）")

    # ── 按北京日期分桶 ───────────────────────────────────────────
    buckets: dict[str, bytearray] = {}
    order: list[str] = []
    cur = None
    for line in raw.splitlines(keepends=True):
        d = cst_day(line) or cur
        if d != cur:
            if d not in buckets:
                buckets[d] = bytearray()
                order.append(d)
            cur = d
        buckets[d] += line

    # ── 自校验 2：分桶后拼回必须等于原文 ─────────────────────────
    rebuilt = b"".join(buckets[d] for d in order)
    lossless = sha(rebuilt) == sha(raw)
    print(f"零丢失 : 分桶重组 == 原文 -> {'OK' if lossless else 'FAIL'}")
    if not lossless:
        return 1

    print("各日行数:", {d: buckets[d].count(b'\n') for d in order})

    if day not in buckets:
        print(f"!! 日志中没有 {day} 的数据（该实例可能当天尚未启动）。")
        return 1

    out = bytes(buckets[day])
    path = os.path.join(out_dir, f"smc_matrix{suffix}_{day.replace('-', '_')}.log")
    with open(path, "wb") as f:
        f.write(out)

    print()
    print("写出   :", path)
    print("字节   :", f"{len(out):,}")
    print("行数   :", out.count(b"\n"))
    print("sha256 :", sha(out))
    first = ANSI.sub(b"", out.splitlines(keepends=True)[0]).decode("utf-8", "replace").strip()
    last = ANSI.sub(b"", out.splitlines(keepends=True)[-1]).decode("utf-8", "replace").strip()
    print("首行   :", first[:120])
    print("末行   :", last[:120])
    return 0


if __name__ == "__main__":
    sys.exit(main())
