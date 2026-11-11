#!/usr/bin/env python3
"""
zsxq-qx Step 3: 用 efinance 拉取价格, 计算发帖后 3 个交易日涨跌幅
输入: signals_with_code.csv
输出: results.csv  (company, code, post_date, t0_date, t0_close, t3_date, t3_close, return_3d, benefit, sentiment)

规则:
  - post_date 为发帖日(MM-DD), 年份 2026
  - 发帖日为非交易日 → 取下一个交易日收盘价为 t0
  - t3 = t0 后第 3 个交易日(不含 t0 当天)
  - return_3d = (close_t3 - close_t0) / close_t0 * 100
"""
import csv
import sys
import time
from pathlib import Path

import efinance as ef
import pandas as pd

INPUT_PATH = Path("/Users/melo/doc-Dgf/zsxq_md/signals_with_code.csv")
OUTPUT_PATH = Path("/Users/melo/doc-Dgf/zsxq_md/results.csv")
YEAR = "2026"
# 港股代码 efinance 需要加前缀
HK_PREFIX_CODES = {"09880", "00175", "09863"}


def get_quote_df(code: str) -> pd.DataFrame:
    """获取股票日K数据, 返回按日期升序的 DataFrame"""
    # 港股代码需要加前缀
    query_code = f"HK:{code}" if code in HK_PREFIX_CODES else code
    df = ef.stock.get_quote_history(query_code, klt=101)  # 101=日K
    if df is None or df.empty:
        return pd.DataFrame()
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.sort_values("日期").reset_index(drop=True)
    return df


def find_t0_t3(df: pd.DataFrame, post_date_str: str):
    """
    给定发帖日 (如 "11-05"), 找到:
      t0 = 发帖日当天(若是交易日) 或 之后第一个交易日
      t3 = t0 之后第 3 个交易日(不含 t0)
    返回 (t0_date, t0_close, t3_date, t3_close) 或 None
    """
    target = pd.Timestamp(f"{YEAR}-{post_date_str}")
    # 找 >= target 的交易日
    future = df[df["日期"] >= target]
    if future.empty:
        return None
    t0_row = future.iloc[0]
    t0_idx = future.index[0]
    # t3 = t0 后第 3 个交易日
    if t0_idx + 3 >= len(df):
        return None
    t3_row = df.iloc[t0_idx + 3]
    return (
        t0_row["日期"].strftime("%Y-%m-%d"),
        float(t0_row["收盘"]),
        t3_row["日期"].strftime("%Y-%m-%d"),
        float(t3_row["收盘"]),
    )


def main():
    with open(INPUT_PATH, encoding="utf-8") as f:
        signals = list(csv.DictReader(f))

    print(f"信号数: {len(signals)}")
    print(f"开始拉取价格...\n")

    results = []
    errors = []
    # 按股票代码缓存行情, 同一股票只拉一次
    quote_cache = {}

    for i, sig in enumerate(signals):
        code = sig["code"]
        company = sig["company"]
        post_date = sig["post_date"]
        sentiment = int(sig["sentiment"])
        benefit = float(sig["benefit"])

        if code not in quote_cache:
            print(f"  [{i+1}/{len(signals)}] 拉取 {company} ({code})...", end=" ", flush=True)
            df = get_quote_df(code)
            quote_cache[code] = df
            print(f"{len(df)} 条" if df is not None and not df.empty else "失败")
            time.sleep(0.3)  # 避免限流

        df = quote_cache[code]
        if df is None or df.empty:
            errors.append(f"{company} ({code}): 无行情数据")
            continue

        res = find_t0_t3(df, post_date)
        if res is None:
            errors.append(f"{company} ({code}): 交易日不足, 无法计算 t3")
            continue

        t0_date, t0_close, t3_date, t3_close = res
        return_3d = round((t3_close - t0_close) / t0_close * 100, 2)

        results.append({
            "company": company,
            "code": code,
            "post_date": post_date,
            "sentiment": sentiment,
            "benefit": benefit,
            "t0_date": t0_date,
            "t0_close": t0_close,
            "t3_date": t3_date,
            "t3_close": t3_close,
            "return_3d": return_3d,
        })
        print(f"    {company:<12s} t0={t0_date}({t0_close:.2f}) → t3={t3_date}({t3_close:.2f}) 涨跌={return_3d:+.2f}%")

    # 写 CSV
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "company", "code", "post_date", "sentiment", "benefit",
            "t0_date", "t0_close", "t3_date", "t3_close", "return_3d",
        ])
        writer.writeheader()
        writer.writerows(results)

    print(f"\n成功: {len(results)}, 失败: {len(errors)}")
    if errors:
        print("错误:")
        for e in errors:
            print(f"  {e}")
    print(f"\n写入: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
