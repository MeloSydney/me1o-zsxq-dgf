#!/usr/bin/env python3
"""
zsxq-qx Step 2: 公司名→股票代码映射
输入: signals.json
输出: signals_with_code.csv  (company, code, benefit, sentiment, post_date)
"""
import json
import csv
import sys
from pathlib import Path

SIGNALS_PATH = Path("/Users/melo/doc-Dgf/zsxq_md/signals.json")
OUTPUT_PATH = Path("/Users/melo/doc-Dgf/zsxq_md/signals_with_code.csv")

NAME_CODE_MAP = {
    # 半导体/AI芯片
    "寒武纪":       "688256",
    "海光信息":      "688041",
    "中芯国际":      "688981",
    "华丰科技":      "688629",
    "兴森科技":      "002436",
    "浪潮信息":      "000977",
    "英维克":        "002837",
    "长电科技":      "600584",
    "江丰电子":      "300666",
    "有研新材":      "600206",
    "珂玛科技":      "301611",
    "富创精密":      "688409",
    "阿石创":        "300706",
    # 光模块
    "中际旭创":      "300308",
    "新易盛":        "300502",
    "天孚通信":      "300394",
    "工业富联":      "601138",
    # 机器人
    "宇树科技":      None,       # 未上市 (2026年初可能已上市, 待查)
    "优必选":        None,        # 港股 09880, 排除
    "绿的谐波":      "688017",
    "双环传动":      "002472",
    "三花智控":      "002050",
    "鸣志电器":      "603728",
    "奥比中光":      "688322",
    "奥普特":        "688686",
    "雷赛智能":      "002990",
    "杰克科技":      "603337",
    "福莱新材":      "605488",
    "兆威机电":      "003021",
    "华依科技":      "688618",
    "德马科技":      "688360",
    "思看科技":      "688583",
    "索辰科技":      "688798",
    "申菱环境":      "301018",
    "高澜股份":      "300499",
    "蓝思科技":      "300433",
    "上纬新材":      "688585",
    "杭叉集团":      "603298",
    # 新能源/电池
    "宁德时代":      "300750",
    "阳光电源":      "300274",
    "亿纬锂能":      "300014",
    "国轩高科":      "002074",
    "天赐材料":      "002709",
    # 隔膜
    "恩捷股份":      "002812",
    "星源材质":      "300568",
    "中材科技":      "002080",
    "璞泰来":        "603659",
    "沧州明珠":      "002108",
    # 矿山绿电
    "紫金龙净":      "601999",   # 待确认, 可能是紫金矿业代码
    "宇通重工":      "600817",
    "金冠电气":      "688517",
    "鸿富瀚":        "301086",
    "宏力达":        "688711",
    "华自科技":      "300490",
    "森特股份":      "603098",
    # 汽车
    "比亚迪":        "002594",
    "奇瑞汽车":      None,       # 未上市
    "吉利汽车":      None,        # 港股 00175, 排除
    "长城汽车":      "601633",    # A股 601633 / 港股 02333
    "上汽集团":      "600104",
    "长安汽车":      "000625",
    "零跑汽车":      None,        # 港股 09863, 排除
    # 电力设备
    "金盘科技":      "688676",
    "伊戈尔":        "002922",
    "中恒电气":      "002364",
    "科华数据":      "002335",
    "四方股份":      "601126",
    "新特电气":      "301120",
    "明阳电气":      "301291",
    "特变电工":      "600089",
    # 无法映射
    "长鑫科技":      None,       # 未上市
    "卧安机器人":    None,       # 未上市
    "博雷顿":        None,       # 未上市
    "科创人工智":    None,       # ETF截断, 排除
    "材料设备主":    None,       # ETF截断, 排除
}


def main():
    signals = json.loads(SIGNALS_PATH.read_text(encoding="utf-8"))

    mapped = []
    skipped = []
    for s in signals:
        company = s["company"]
        code = NAME_CODE_MAP.get(company)
        if code is None:
            skipped.append(company)
            continue
        mapped.append({
            "company": company,
            "code": code,
            "benefit": s["benefit"],
            "sentiment": s["sentiment"],
            "post_date": s["post_date"],
        })

    # 同公司同日去重取情绪最高
    seen = {}
    for m in mapped:
        key = (m["code"], m["post_date"])
        if key not in seen or m["sentiment"] > seen[key]["sentiment"]:
            seen[key] = m
    deduped = list(seen.values())

    # 按日期+情绪排序
    deduped.sort(key=lambda x: (x["post_date"], -x["sentiment"]))

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["company", "code", "benefit", "sentiment", "post_date"])
        writer.writeheader()
        writer.writerows(deduped)

    print(f"原始信号: {len(signals)}")
    print(f"映射成功: {len(mapped)}")
    print(f"去重后:   {len(deduped)}")
    print(f"跳过(未上市/ETF): {sorted(set(skipped))}")
    print(f"\n去重后信号:")
    for m in deduped:
        print(f"  {m['post_date']} | {m['company']:<10s} ({m['code']}) | 受益度={m['benefit']:.1f} 情绪={m['sentiment']:3d}")
    print(f"\n写入: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
