#!/usr/bin/env python3
"""知识星球 API 导出脚本 - 使用 zsxq API 直接获取完整帖子，无需浏览器展开"""

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

GROUP_ID = "15522441811252"
API_BASE = "https://api.zsxq.com/v2/groups"
OUTPUT_DIR = Path("/Users/melo/doc-Dgf/zsxq_md")
CST = timezone(timedelta(hours=8))


# 默认 .env 路径（存放 zsxq_access_token）
DEFAULT_ENV_FILE = Path("/Users/melo/src-skills/src-zsxq/me1o-zsxq-dgf/zsxq-export/.env")


def read_token_from_env(env_path: Path) -> str | None:
    """从 .env 文件读取 zsxq_access_token，支持 KEY=VALUE 和纯 token 两种格式"""
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # KEY=VALUE 格式
        if "=" in line:
            key, _, val = line.partition("=")
            if key.strip().upper() in ("ZSXQ_ACCESS_TOKEN", "TOKEN", "ACCESS_TOKEN"):
                return val.strip().strip("\"'\"")
        else:
            # 纯 token（UUID_UUID 格式）
            if re.match(r"^[0-9A-Fa-f-]+_[0-9A-Fa-f]+$", line):
                return line
    return None



def decode_e_tags(s: str) -> str:
    """解码知识星球自定义 <e> 标签为 Markdown"""
    if not s:
        return ""
    # Bold: <e type="text_bold" title="xxx" />
    s = re.sub(
        r'<e type="text_bold" title="([^"]*?)"\s*/>',
        lambda m: "**" + urllib.parse.unquote(m.group(1)) + "**",
        s,
    )
    # Hashtag: <e type="hashtag" hid="xxx" title="xxx" />
    s = re.sub(
        r'<e type="hashtag"[^>]*title="([^"]*?)"\s*/>',
        lambda m: urllib.parse.unquote(m.group(1)),
        s,
    )
    # Mention: <e type="mention" uid="xxx" title="@xxx" />
    s = re.sub(
        r'<e type="mention"[^>]*title="([^"]*?)"\s*/>',
        lambda m: urllib.parse.unquote(m.group(1)),
        s,
    )
    # Other e tags with title
    s = re.sub(
        r'<e type="[^"]*"[^>]*title="([^"]*?)"[^>]*?/?>',
        lambda m: urllib.parse.unquote(m.group(1)),
        s,
    )
    # Remove remaining e tags
    s = re.sub(r"<e[^>]*/?>", "", s)
    return s


def fetch_topics(token: str, start_date: str, end_date: str) -> list[dict]:
    """获取指定日期范围内的所有帖子"""
    headers = {
        "Cookie": f"zsxq_access_token={token}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": f"https://wx.zsxq.com/group/{GROUP_ID}",
        "Origin": "https://wx.zsxq.com",
    }

    all_topics = []
    end_time = None
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=CST)
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=CST
    )

    while True:
        url = f"{API_BASE}/{GROUP_ID}/topics?scope=all&count=20"
        if end_time:
            url += f"&end_time={urllib.parse.quote(end_time, safe='')}"

        req = urllib.request.Request(url, headers=headers)
        # 翻页重试：API 偶尔返回内部错误，最多重试 3 次
        data = None
        for retry in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if data.get("succeeded"):
                    break
                # API 返回业务错误
                err_msg = data.get("error", "未知错误")
                if "1059" in str(data.get("error_code", "")):
                    print(f"  API 限流，等待 10 秒后重试 ({retry+1}/3)...", file=sys.stderr)
                    import time; time.sleep(10)
                    continue
                print(f"API 请求失败: {err_msg}，等待 5 秒后重试 ({retry+1}/3)...", file=sys.stderr)
                import time; time.sleep(5)
            except urllib.error.HTTPError as e:
                print(f"  HTTP {e.code} 错误，等待 5 秒后重试 ({retry+1}/3)...", file=sys.stderr)
                import time; time.sleep(5)
            except Exception as e:
                print(f"  请求异常: {e}，等待 5 秒后重试 ({retry+1}/3)...", file=sys.stderr)
                import time; time.sleep(5)

        if data is None or not data.get("succeeded"):
            print(f"翻页重试 3 次仍失败，已获取 {len(all_topics)} 条帖子，继续处理", file=sys.stderr)
            break

        topics = data["resp_data"].get("topics", [])
        if not topics:
            break

        should_stop = False
        for t in topics:
            ct = t.get("create_time", "")
            try:
                topic_dt = datetime.fromisoformat(ct)
            except ValueError:
                continue

            if topic_dt > end_dt:
                continue
            if topic_dt < start_dt:
                should_stop = True
                break

            all_topics.append(t)

        if should_stop or not topics:
            break

        is_end = data["resp_data"].get("is_end")
        if is_end is True:
            break

        last = topics[-1]
        end_time = last.get("create_time", "")
        if not end_time:
            break

        import time
        time.sleep(2)

    return all_topics


def extract_score(text: str) -> float | None:
    """从文本中提取能量评分"""
    m = re.search(r"能量评分(\d+(?:\.\d+)?)分", text)
    if m:
        return float(m.group(1))
    return None


def extract_tags(text: str) -> list[str]:
    """从原始文本中提取标签"""
    tags = []
    for m in re.finditer(r'<e type="hashtag"[^>]*title="([^"]*?)"\s*/>', text):
        tags.append(urllib.parse.unquote(m.group(1)))
    return tags


def extract_files(topic: dict) -> list[str]:
    """提取附件文件名"""
    files = []
    talk = topic.get("talk", {})
    for f in talk.get("files", []):
        files.append(f.get("name", ""))
    return files


def extract_comments(topic: dict) -> list[str]:
    """提取评论"""
    comments = []
    show_comments = topic.get("show_comments", [])
    for c in show_comments:
        owner = c.get("owner", {}).get("name", "")
        text = decode_e_tags(c.get("text", ""))
        if text:
            comments.append(f"{owner}：{text}")
    return comments


def extract_post_title(text: str, ttype: str) -> str:
    """提取帖子标题（15字以内）"""
    # 去掉能量评分前缀
    cleaned = re.sub(r"\*\*能量评分\d+(?:\.\d+)?分[。、]?\（[^）]*\）?\*\*", "", text)
    cleaned = re.sub(r"能量评分\d+(?:\.\d+)?分[。、]?\（[^）]*\）?", "", cleaned)
    cleaned = cleaned.strip()

    # 研报类：提取《》中的研报主题
    m = re.search(r"《([^》]+)》", cleaned)
    if m:
        title = m.group(1)
        return title[:15]

    # 提问类：提取问题核心
    if ttype == "q&a" or "？" in cleaned or "?" in cleaned:
        qm = re.search(r"[，。！\n]([^，。！？\n]{2,15}[？?])", cleaned)
        if qm:
            return qm.group(1)[:15]
        # 取前15字
        first = re.split(r"[。\n]", cleaned)[0].strip()
        return first[:15]

    # 取第一句
    first = re.split(r"[。\n]", cleaned)[0].strip()
    if len(first) > 15:
        first = first[:15]
    return first or "未命名"


def format_topic(topic: dict) -> dict | None:
    """将单个 topic 格式化为输出格式"""
    ttype = topic.get("type", "")
    talk = topic.get("talk", {})
    question = topic.get("question", {})
    answer = topic.get("answer", {})

    # 提取文本
    raw_text = talk.get("text", "") if talk else ""
    q_raw = question.get("text", "") if question else ""
    a_raw = answer.get("text", "") if answer else ""

    # 解码标签
    text = decode_e_tags(raw_text)
    q_text = decode_e_tags(q_raw)
    a_text = decode_e_tags(a_raw)

    # 合并全文用于评分提取
    full_raw = raw_text + " " + a_raw
    score = extract_score(decode_e_tags(full_raw))

    # 提取标签和附件
    tags = extract_tags(raw_text) + extract_tags(a_raw)
    files = extract_files(topic)

    # 提取日期和作者
    created = topic.get("create_time", "")
    if ttype == "q&a":
        owner = question.get("owner", {}).get("name", "") if question else ""
        answer_owner = answer.get("owner", {}).get("name", "") if answer else ""
    else:
        owner = talk.get("owner", {}).get("name", "") if talk else ""
        answer_owner = ""

    # 构建完整帖子文本
    if ttype == "q&a":
        full_text = ""
        if q_text:
            full_text += f"**{owner} 提问：**\n\n{q_text}\n\n"
        if a_text:
            full_text += f"**{answer_owner} 回答：**\n\n{a_text}"
    else:
        full_text = text

    # 提取标题；提问帖只基于问题正文，避免把“某某提问”署名当作标题
    title_source = q_text if ttype == "q&a" else full_text
    title = extract_post_title(title_source, ttype)

    # 提取评论
    comments = extract_comments(topic)

    return {
        "type": ttype,
        "created": created,
        "owner": owner,
        "score": score,
        "title": title,
        "text": full_text,
        "tags": tags,
        "files": files,
        "comments": comments,
    }


def generate_markdown(
    posts: list[dict],
    qa_posts: list[dict],
    start_date: str,
    end_date: str,
    total_count: int,
    filtered_count: int,
    no_filter: bool,
) -> str:
    """生成 Markdown 文件内容，用户提问单独归入专属章节。"""
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M")

    if no_filter:
        count_line = (
            f"> 星主帖子：{len(posts)} 篇 | 用户提问：{len(qa_posts)} 篇"
            f"（API 返回 {total_count} 条）"
        )
    else:
        count_line = (
            f"> 星主帖子：{len(posts)} 篇（评分过滤 {filtered_count} 篇）"
            f" | 用户提问：{len(qa_posts)} 篇（不参与评分过滤）"
        )

    lines = [
        "# 大锅饭与小伙伴的进步空间（原始数据）",
        "",
        f"> 来源：https://wx.zsxq.com/group/{GROUP_ID}",
        f"> 导出时间：{now}",
        f"> 日期范围：{start_date} ~ {end_date}",
        count_line,
        "",
        "---",
    ]

    def append_post(post: dict, question: bool = False) -> None:
        score_str = f"{post['score']}" if post["score"] is not None else "无"
        if post["created"]:
            dt = datetime.fromisoformat(post["created"])
            time_str = dt.strftime("%m-%d %H:%M")
        else:
            time_str = "未知"

        if question:
            lines.append(f"### ❓ ⭐ {score_str}分 | {time_str} | {post['title']}")
        else:
            lines.append(f"## ⭐ {score_str}分 | {time_str} | {post['title']}")
        lines.append("")
        lines.append(post["text"])

        if post["tags"]:
            lines.append("")
            lines.append(f"**标签**：{' '.join(post['tags'])}")

        if post["files"]:
            lines.append("")
            lines.append(f"**附件**：{', '.join(post['files'])}")

        if post["comments"]:
            lines.append("")
            lines.append("评论原文：")
            for comment in post["comments"]:
                lines.append(comment)

        lines.append("")
        lines.append("---")
        lines.append("")

    for post in posts:
        append_post(post)

    if qa_posts:
        lines.extend(
            [
                "## 🙋 用户提问",
                "",
                "> 本章节保留日期范围内抓取到的全部用户提问及回答，按发布时间降序排列，不参与能量评分过滤。",
                "",
                "---",
                "",
            ]
        )
        for post in qa_posts:
            append_post(post, question=True)

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="知识星球帖子导出")
    parser.add_argument("token", nargs="?", default=None, help="zsxq_access_token（可选，不提供则从 .env 读取）")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE, help="token 所在的 .env 文件路径")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=3, help="最近N天（默认3天）")
    parser.add_argument("--no-filter", action="store_true", help="不按能量评分过滤，保留所有帖子")
    parser.add_argument("--min-score", type=float, default=None, help="最低能量评分过滤阈值（默认不过滤）")
    args = parser.parse_args()

    # 解析 token：优先使用命令行参数，否则从 .env 文件读取
    token = args.token
    if not token:
        token = read_token_from_env(args.env_file)
        if token:
            print(f"已从 {args.env_file} 读取 token")
        else:
            parser.error(
                "未提供 token，且无法从 .env 文件读取。\n"
                f"请确认 {args.env_file} 存在并包含 zsxq_access_token，\n"
                "或通过命令行参数传入 token。"
            )

    # 计算日期范围
    now = datetime.now(CST)
    if args.start and args.end:
        start_date = args.start
        end_date = args.end
    else:
        end_dt = now
        start_dt = end_dt - timedelta(days=args.days - 1)
        start_date = start_dt.strftime("%Y-%m-%d")
        end_date = end_dt.strftime("%Y-%m-%d")

    # 确定过滤模式
    no_filter = args.no_filter or (args.min_score is None)
    min_score = args.min_score if args.min_score is not None else 0

    print(f"正在获取 {start_date} ~ {end_date} 的帖子...")
    if no_filter:
        print("模式：不过滤评分，保留所有帖子")
    else:
        print(f"模式：过滤评分 >= {min_score}")

    # 获取帖子
    topics = fetch_topics(token, start_date, end_date)
    print(f"API 返回 {len(topics)} 条帖子")

    # 格式化：星主帖子与用户提问分别保存
    all_posts = []
    qa_posts = []
    filtered_count = 0
    for topic in topics:
        post = format_topic(topic)
        if post is None:
            continue

        # 日期过滤
        if post["created"]:
            post_date = post["created"][:10]
            if post_date < start_date or post_date > end_date:
                filtered_count += 1
                continue

        # 用户提问全部保留到独立章节，不参与能量评分过滤
        if post["type"] == "q&a":
            qa_posts.append(post)
            continue

        # 能量评分过滤仅作用于星主帖子，且只在指定 --min-score 时生效
        if not no_filter:
            if post["score"] is None or post["score"] < min_score:
                filtered_count += 1
                continue

        all_posts.append(post)

    # 星主帖子：评分降序，同评分按时间降序；用户提问：按时间降序
    all_posts.sort(key=lambda post: post["created"], reverse=True)
    all_posts.sort(
        key=lambda post: post["score"] if post["score"] is not None else -1,
        reverse=True,
    )
    qa_posts.sort(key=lambda post: post["created"], reverse=True)

    print(
        f"保留 {len(all_posts)} 篇星主帖子"
        + (f"（评分过滤 {filtered_count} 篇）" if filtered_count > 0 else "")
    )
    print(f"保留用户提问（q&a）帖子：{len(qa_posts)} 篇，写入独立章节")

    # 生成 Markdown
    md = generate_markdown(
        all_posts,
        qa_posts,
        start_date,
        end_date,
        len(topics),
        filtered_count,
        no_filter,
    )

    # 写入文件
    mmdd = now.strftime("%m%d")
    output_path = OUTPUT_DIR / f"{mmdd}_大锅饭_raw_{start_date}_{end_date}.md"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md, encoding="utf-8")

    print(f"\n导出完成！")
    print(f"文件路径：{output_path}")
    print(f"星主帖子数量：{len(all_posts)}")
    print(f"用户提问数量：{len(qa_posts)}（已写入独立章节）")
    if not no_filter:
        print(f"评分过滤：{filtered_count} 篇星主帖子（评分<{min_score}或无评分）")
    print(f"日期范围：{start_date} ~ {end_date}")
    print(f"\n可使用 zsxq-analyse skill 对 raw 文件进行浓缩总结")


if __name__ == "__main__":
    main()
