#!/usr/bin/env python3
"""
zsxq-qx Step 4: 统计分析 — 验证"情绪热度高→大概率上涨"猜想
输入: results.csv
输出: 1106_sentiment_report.md
"""
import csv
import statistics
from pathlib import Path
from collections import defaultdict

INPUT_PATH = Path("/Users/melo/doc-Dgf/zsxq_md/results.csv")
OUTPUT_PATH = Path("/Users/melo/doc-Dgf/1106_sentiment_report.md")


def main():
    with open(INPUT_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        r["sentiment"] = int(r["sentiment"])
        r["benefit"] = float(r["benefit"])
        r["return_3d"] = float(r["return_3d"])

    n = len(rows)
    returns = [r["return_3d"] for r in rows]
    sentiments = [r["sentiment"] for r in rows]

    # 全局统计
    mean_ret = statistics.mean(returns)
    median_ret = statistics.median(returns)
    win_count = sum(1 for x in returns if x > 0)
    loss_count = sum(1 for x in returns if x < 0)
    flat_count = n - win_count - loss_count

    # Spearman 相关性 (手动实现)
    def spearman(xs, ys):
        n = len(xs)
        rx = [sorted(xs).index(x) + 1 for x in xs]
        ry = [sorted(ys).index(y) + 1 for y in ys]
        mx, my = statistics.mean(rx), statistics.mean(ry)
        num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
        dx = (sum((a - mx) ** 2 for a in rx)) ** 0.5
        dy = (sum((b - my) ** 2 for b in ry)) ** 0.5
        return num / (dx * dy) if dx * dy > 0 else 0

    rho_sent = spearman(sentiments, returns)
    rho_ben = spearman([r["benefit"] for r in rows], returns)

    # 分组分析: 按情绪热度分组
    groups = {
        "高情绪(≥80)":  [r for r in rows if r["sentiment"] >= 80],
        "中情绪(65-79)": [r for r in rows if 65 <= r["sentiment"] < 80],
        "低情绪(<65)":  [r for r in rows if r["sentiment"] < 65],
    }

    group_stats = {}
    for name, grp in groups.items():
        if not grp:
            continue
        rets = [r["return_3d"] for r in grp]
        wins = sum(1 for x in rets if x > 0)
        group_stats[name] = {
            "n": len(grp),
            "win_rate": wins / len(rets) * 100,
            "mean_ret": statistics.mean(rets),
            "median_ret": statistics.median(rets),
        }

    # 按受益度分组
    ben_groups = {
        "高受益(≥8.5)":  [r for r in rows if r["benefit"] >= 8.5],
        "中受益(7.5-8.4)": [r for r in rows if 7.5 <= r["benefit"] < 8.5],
        "低受益(<7.5)":  [r for r in rows if r["benefit"] < 7.5],
    }
    ben_stats = {}
    for name, grp in ben_groups.items():
        if not grp:
            continue
        rets = [r["return_3d"] for r in grp]
        wins = sum(1 for x in rets if x > 0)
        ben_stats[name] = {
            "n": len(grp),
            "win_rate": wins / len(rets) * 100,
            "mean_ret": statistics.mean(rets),
            "median_ret": statistics.median(rets),
        }

    # 按日期分组
    date_groups = defaultdict(list)
    for r in rows:
        date_groups[r["post_date"]].append(r)
    date_stats = {}
    for date, grp in sorted(date_groups.items()):
        rets = [r["return_3d"] for r in grp]
        wins = sum(1 for x in rets if x > 0)
        date_stats[date] = {
            "n": len(grp),
            "win_rate": wins / len(rets) * 100,
            "mean_ret": statistics.mean(rets),
        }

    # 生成报告
    lines = []
    lines.append("# 情绪热度 vs 3日涨跌幅 验证报告\n")
    lines.append(f"> 数据来源: 知识星球「大锅饭」2026-10-28~10-30 帖子 OCR 表格\n")
    lines.append(f"> 样本: {n} 条 A 股信号 (排除港股/ETF/未上市)\n")
    lines.append(f"> 规则: t0=发帖日(或下一交易日), t3=t0后第3个交易日, return=(close_t3-close_t0)/close_t0\n")

    lines.append("\n## 一、全局统计\n")
    lines.append(f"| 指标 | 值 |")
    lines.append(f"|------|----|")
    lines.append(f"| 样本数 | {n} |")
    lines.append(f"| 平均涨跌 | {mean_ret:+.2f}% |")
    lines.append(f"| 中位数涨跌 | {median_ret:+.2f}% |")
    lines.append(f"| 上涨数 | {win_count} ({win_count/n*100:.1f}%) |")
    lines.append(f"| 下跌数 | {loss_count} ({loss_count/n*100:.1f}%) |")
    lines.append(f"| 平盘数 | {flat_count} ({flat_count/n*100:.1f}%) |")

    lines.append("\n## 二、相关性分析 (Spearman)\n")
    lines.append(f"| 维度 | 相关系数 ρ | 含义 |")
    lines.append(f"|------|-----------|------|")
    lines.append(f"| 情绪热度 → 3日涨跌 | {rho_sent:+.4f} | {'弱正相关' if 0 < rho_sent < 0.3 else '弱负相关' if -0.3 < rho_sent < 0 else '显著' if abs(rho_sent) >= 0.3 else '无关'} |")
    lines.append(f"| 受益度 → 3日涨跌 | {rho_ben:+.4f} | {'弱正相关' if 0 < rho_ben < 0.3 else '弱负相关' if -0.3 < rho_ben < 0 else '显著' if abs(rho_ben) >= 0.3 else '无关'} |")

    lines.append("\n## 三、情绪热度分组胜率\n")
    lines.append(f"| 分组 | 样本 | 胜率 | 平均涨跌 | 中位数涨跌 |")
    lines.append(f"|------|------|------|---------|-----------|")
    for name, s in group_stats.items():
        lines.append(f"| {name} | {s['n']} | {s['win_rate']:.1f}% | {s['mean_ret']:+.2f}% | {s['median_ret']:+.2f}% |")

    lines.append("\n## 四、受益度分组胜率\n")
    lines.append(f"| 分组 | 样本 | 胜率 | 平均涨跌 | 中位数涨跌 |")
    lines.append(f"|------|------|------|---------|-----------|")
    for name, s in ben_stats.items():
        lines.append(f"| {name} | {s['n']} | {s['win_rate']:.1f}% | {s['mean_ret']:+.2f}% | {s['median_ret']:+.2f}% |")

    lines.append("\n## 五、按发帖日期分组\n")
    lines.append(f"| 日期 | 样本 | 胜率 | 平均涨跌 |")
    lines.append(f"|------|------|------|---------|")
    for date, s in sorted(date_stats.items()):
        lines.append(f"| {date} | {s['n']} | {s['win_rate']:.1f}% | {s['mean_ret']:+.2f}% |")

    # 明细表
    lines.append("\n## 六、全部信号明细\n")
    lines.append(f"| 日期 | 公司 | 代码 | 情绪 | 受益度 | t0收盘 | t3收盘 | 3日涨跌 |")
    lines.append(f"|------|------|------|------|--------|--------|--------|---------|")
    for r in sorted(rows, key=lambda x: (x["post_date"], -x["sentiment"])):
        lines.append(f"| {r['post_date']} | {r['company']} | {r['code']} | {r['sentiment']} | {r['benefit']:.1f} | {float(r['t0_close']):.2f} | {float(r['t3_close']):.2f} | {r['return_3d']:+.2f}% |")

    # 结论
    lines.append("\n## 七、结论\n")
    high_grp = group_stats.get("高情绪(≥80)", {})
    low_grp = group_stats.get("低情绪(<65)", {})
    if high_grp and low_grp:
        lines.append(f"- **情绪热度 vs 涨跌**: Spearman ρ = {rho_sent:+.4f}，")
        if rho_sent > 0:
            lines.append(f"呈弱正相关，情绪越高涨跌越好，但不显著。\n")
        else:
            lines.append(f"呈弱负相关，情绪越高反而跌得越多（可能反映追高风险）。\n")
        lines.append(f"- **分组对比**: 高情绪组({high_grp['n']}条)胜率 {high_grp['win_rate']:.1f}%、平均 {high_grp['mean_ret']:+.2f}%；低情绪组({low_grp['n']}条)胜率 {low_grp['win_rate']:.1f}%、平均 {low_grp['mean_ret']:+.2f}%。\n")
    
    # 市场背景
    lines.append(f"- **市场背景**: 10-28~11-04 期间大盘整体下跌（多数样本涨跌为负），需结合大盘走势判断情绪热度的相对预测力。\n")
    lines.append(f"- **样本局限**: 仅3天数据、73条样本，统计意义有限；情绪热度可能更反映短期关注度而非长期方向。\n")

    report = "\n".join(lines)
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n写入: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
