#!/usr/bin/env python3
"""
zsxq-qx Step 1: 从 raw markdown 中提取情绪热度信号
输入: raw markdown 文件 (含 OCR code block 空间布局表格)
输出: signals.json  [{company, sentiment, benefit, post_date, desc}, ...]

解析策略:
  1. 找 code block 内含 "受益度" 和 "情绪热度" 的表头行
  2. 计算受益度/情绪热度列的 x 位置(字符偏移)
  3. 对每行提取 (leading_spaces, benefit, sentiment, first_word)
  4. 公司行 = leading_spaces <= 2 的行
  5. 对每个公司行, b/s 可能在本行、前一行(续行)或后一行(续行)
  6. 过滤 ETF 和异常值
"""
import json
import re
import sys
from pathlib import Path

RAW_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    Path("/Users/melo/doc-Dgf/zsxq_md/1106_大锅饭_raw_2026-10-28_2026-10-30.md")
OUTPUT_PATH = Path("/Users/melo/doc-Dgf/zsxq_md/signals.json")


def find_post_date(lines: list, idx: int) -> str:
    """从 idx 向前查找最近的发帖时间行, 返回 MM-DD"""
    for i in range(idx, -1, -1):
        m = re.search(r'(\d{2}-\d{2})\s+\d{2}:\d{2}', lines[i])
        if m:
            return m.group(1)
        m = re.search(r'20\d{2}-(\d{2}-\d{2})', lines[i])
        if m:
            return m.group(1)
    return ""


def extract_num_at(line: str, pos: int, search_range: int = 10) -> str | None:
    """在 line 的 pos 位置附近找数字"""
    start = max(0, pos - 3)
    end = min(len(line), pos + search_range)
    segment = line[start:end]
    m = re.search(r'(\d+\.?\d*)', segment)
    return m.group(1) if m else None


def parse_block(block_lines: list) -> list[tuple]:
    """
    解析一个 OCR block, 返回 [(leading_spaces, benefit_str, sentiment_str, first_word, line), ...]
    """
    # 找表头行
    header_idx = -1
    for i, line in enumerate(block_lines):
        if "受益度" in line and "情绪热度" in line:
            header_idx = i
            break
    if header_idx < 0:
        return []

    header = block_lines[header_idx]
    pos_benefit = header.find("受益度")
    pos_sentiment = header.find("情绪热度")
    if pos_benefit < 0 or pos_sentiment < 0:
        return []

    rows = []
    for j in range(header_idx + 1, len(block_lines)):
        line = block_lines[j]
        if not line.strip():
            continue
        leading_spaces = len(line) - len(line.lstrip())
        b = extract_num_at(line, pos_benefit)
        s = extract_num_at(line, pos_sentiment)
        stripped = line.strip()
        first_word = stripped.split()[0] if stripped else ""
        rows.append((leading_spaces, b, s, first_word, line))
    return rows


def is_valid_company(name: str, b: float | None, s: int | None) -> bool:
    """过滤非公司名和异常值"""
    if b is None or s is None:
        return False
    if b > 10 or b < 1:
        return False
    if s > 100 or s < 1:
        return False
    # 排除 ETF
    if "ETF" in name or "etf" in name:
        return False
    # 排除明显非公司名的描述文本 (通常较长或含特定关键词)
    if len(name) > 8:
        return False
    # 排除 "机器人相关" 等泛称
    if name in ("机器人相关", "港股通汽车", "储能电池"):
        return False
    if "中证" in name or "国证" in name:
        return False
    return True


def extract_signals(raw_text: str) -> list:
    lines = raw_text.split("\n")
    signals = []

    in_code_block = False
    code_block_start = -1
    code_lines = []

    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_block_start = i
                code_lines = []
            else:
                in_code_block = False
                rows = parse_block(code_lines)
                if rows:
                    post_date = find_post_date(lines, code_block_start)
                    if post_date:
                        # 处理 rows: 找公司行(sp<=2), 补齐 b/s
                        for ri, (sp, b, s, first_word, raw_line) in enumerate(rows):
                            if sp > 2:
                                continue  # 续行, 不是公司行

                            company = first_word
                            benefit_str = b
                            sentiment_str = s

                            # 从前一行(续行)补齐缺失的 b 或 s
                            if (benefit_str is None or sentiment_str is None) and ri > 0:
                                prev_sp, prev_b, prev_s, _, _ = rows[ri - 1]
                                if prev_sp > 2:  # 确认是续行
                                    if benefit_str is None:
                                        benefit_str = prev_b
                                    if sentiment_str is None:
                                        sentiment_str = prev_s

                            # 从后一行(续行)补齐仍缺失的 b 或 s
                            if (benefit_str is None or sentiment_str is None) and ri + 1 < len(rows):
                                next_sp, next_b, next_s, _, _ = rows[ri + 1]
                                if next_sp > 2:  # 确认是续行
                                    if benefit_str is None:
                                        benefit_str = next_b
                                    if sentiment_str is None:
                                        sentiment_str = next_s

                            # 转换和验证
                            try:
                                benefit = float(benefit_str) if benefit_str else None
                                sentiment = int(sentiment_str) if sentiment_str else None
                            except (ValueError, TypeError):
                                continue

                            if not is_valid_company(company, benefit, sentiment):
                                continue

                            signals.append({
                                "company": company,
                                "benefit": benefit,
                                "sentiment": sentiment,
                                "post_date": post_date,
                                "desc": "",
                            })
                code_lines = []
        elif in_code_block:
            code_lines.append(line)

    return signals


def main():
    if not RAW_PATH.exists():
        print(f"ERROR: raw file not found: {RAW_PATH}", file=sys.stderr)
        sys.exit(1)

    raw_text = RAW_PATH.read_text(encoding="utf-8")
    signals = extract_signals(raw_text)

    companies = set(s["company"] for s in signals)
    print(f"提取信号数: {len(signals)}")
    print(f"唯一公司数: {len(companies)}")

    from collections import Counter
    date_dist = Counter(s["post_date"] for s in signals)
    print("日期分布: ", end="")
    for d, c in sorted(date_dist.items()):
        print(f"{d}={c} ", end="")
    print()

    print("\n所有信号:")
    for i, s in enumerate(signals):
        print(f"  [{i:2d}] {s['post_date']} | {s['company']:<10s} | 受益度={s['benefit']:.1f} 情绪={s['sentiment']:3d}")

    OUTPUT_PATH.write_text(json.dumps(signals, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写入: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
