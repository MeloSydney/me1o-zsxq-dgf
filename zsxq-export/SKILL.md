---
name: zsxq-export
description: 抓取知识星球"大锅饭与小伙伴的进步空间"页面内容，按日期和能量评分过滤后导出为本地原始 markdown 文件（raw）。当用户提到"导出知识星球"、"抓取星球"、"zsxq 导出"、"保存星球帖子"、"知识星球 markdown"时应触发此 skill。
version: 1.0.0
allowed-tools: Bash, Read, Write, Glob
argument-hint: "[日期或日期范围] 例如: 3d、7d、2026-05-01:2026-05-12"
---

# 知识星球内容导出（原始数据）

将「大锅饭与小伙伴的进步空间」星球帖子通过 **zsxq API** 直接获取，按日期和能量评分过滤后，保存为本地原始 markdown 文件。**此 skill 只负责抓取和过滤，不做任何总结或浓缩。**

**固定星球地址**：`https://wx.zsxq.com/group/15522441811252`
**固定星球 ID**：`15522441811252`

## 前置条件

**用户需提前提供：**
- 知识星球 `zsxq_access_token`（从浏览器 Cookie 中获取：F12 → Application → Cookies → `https://wx.zsxq.com` → `zsxq_access_token`）

如果用户未提供 token，提示用户：**"请提供 zsxq_access_token（从浏览器 Cookie 中复制），格式为 UUID_UUID"**

**不再需要浏览器展开操作**——API 返回的帖子正文是完整的，无需点击"展开全部"。

## 输入参数

`$ARGUMENTS` 格式：`[日期过滤]`

### 日期过滤（可选）

| 格式 | 示例 | 含义 |
|------|------|------|
| 单日 | `2026-05-05` | 只导出该日帖子 |
| 日期范围 | `2026-05-01:2026-05-05` | 导出从起始日到结束日的帖子 |
| 相对天数 | `1d` / `3d` / `7d` | 导出最近 N 天的帖子 |
| 无参数 | 留空 | 默认导出最近 3 天 |

## 执行步骤

### 0. 获取当前日期

**首先必须获取今天的日期**，作为后续所有日期计算的基准：

```bash
date +%Y-%m-%d
```

将获取到的日期记为 `today`（如 `2026-07-13`），同时提取 `MMDD` 部分（如 `0713`）用于输出文件命名。后续所有日期解析都基于此 `today` 计算。

### 1. 清除旧文件

**每次调用必须重新拉取，不使用任何缓存。** 在调用 API 之前，先删除同日期范围可能已存在的旧 raw 文件，避免残留数据干扰：

```bash
rm -f /Users/melo/doc-Dgf/zsxq_md/{MMDD}_大锅饭_raw_{start_date}_{end_date}.md
```

即使同一天内多次调用，也要先删除再重新拉取，确保数据是最新的。

### 2. 解析参数

从 `$ARGUMENTS` 中解析日期过滤条件，**以步骤 0 获取的 `today` 为基准**：

- 识别日期格式（YYYY-MM-DD、YYYY-MM-DD:YYYY-MM-DD、Nd）
- 相对天数 `Nd`：`start_date = today - (N-1)天`，`end_date = today`（含首尾）
  - 例如 `4d` 且 today=2026-07-13 → start_date=2026-07-10, end_date=2026-07-13
- 单日 `YYYY-MM-DD`：`start_date = end_date = 该日期`
- 日期范围 `YYYY-MM-DD:YYYY-MM-DD`：直接使用
- 如果没有日期参数，默认为最近 3 天（`start_date = today - 2天`，`end_date = today`）
- 计算出最终的 start_date 和 end_date（含首尾）

### 3. 调用 zsxq API 获取帖子

使用 `/Users/melo/doc-Dgf/zsxq_export.py` 脚本执行导出：

```bash
python3 /Users/melo/doc-Dgf/zsxq_export.py "<ACCESS_TOKEN>" --days <N>
```

或指定日期范围：

```bash
python3 /Users/melo/doc-Dgf/zsxq_export.py "<ACCESS_TOKEN>" --start 2026-05-01 --end 2026-05-05
```

**脚本功能说明：**
- 调用 `https://api.zsxq.com/v2/groups/{group_id}/topics` API 获取帖子
- 自动翻页（使用 `end_time` 参数，格式为 ISO 8601 URL 编码）
- 每页 20 条，翻页间隔 2 秒（避免触发限流）
- 自动解码知识星球自定义 `<e>` 标签（text_bold → **加粗**，hashtag → 标签文本，mention → @用户名）
- 按日期范围过滤帖子
- 按能量评分过滤（≥ 8 分保留，< 8 分或无评分过滤掉）
- 按能量评分降序排序，同评分按时间降序
- 提取帖子发布时间戳（MM-DD HH:MM 格式）
- 提取标签、附件文件名、评论
- 生成 markdown 文件，每条帖子标题格式：`## ⭐ {评分}分 | {MM-DD HH:MM} | {标题}`

**API 关键参数：**
- URL: `https://api.zsxq.com/v2/groups/15522441811252/topics?scope=all&count=20`
- 翻页: `&end_time=<URL编码的ISO时间戳>`（如 `2026-05-21T11%3A08%3A10.610%2B08%3A00`）
- Headers: `Cookie: zsxq_access_token=<TOKEN>`, `User-Agent`, `Referer`, `Origin`
- 帖子类型: `talk`（星主发帖）、`q&a`（问答）
- 能量评分在 `talk.text` 或 `answer.text` 中，格式为 `能量评分X.X分`
- 评论区在 `show_comments` 字段中
- 翻页终止条件: `is_end === True` 或帖子日期超出范围

**如果 API 返回错误（code 1059 表示限流）：**
- 等待 5-10 秒后重试
- 如果持续失败，提示用户稍后再试

### 4. 验证输出

检查生成的 markdown 文件：
- 确认帖子数量与 API 返回的过滤结果一致
- 确认帖子正文完整（未被截断）
- 确认能量评分提取正确
- 确认标签和附件信息完整

### 5. 输出结果

告知用户：
- 导出的文件路径（含 raw 标识）
- 导出的帖子数量（过滤后）
- 被过滤掉的帖子数量（能量评分 < 8 分或无评分）
- 日期范围
- 提示用户可使用 `zsxq-analyse` skill 对 raw 文件进行浓缩总结

## 输出文件

**文件路径**：`/Users/melo/doc-Dgf/zsxq_md/{MMDD}_大锅饭_raw_{start_date}_{end_date}.md`

其中 `{MMDD}` 为当前日期的月日（如 `0522`），遵循全局文件命名规则。文件名中的 `raw` 表示这是未经加工的原始数据。

## 注意事项

- **不再需要浏览器操作**——所有数据通过 API 获取，帖子正文完整无需展开
- API 有请求频率限制，翻页间隔 2 秒，避免触发 code 1059 限流
- `end_time` 参数必须使用 ISO 8601 格式并进行 URL 编码（`:` → `%3A`，`+` → `%2B`）
- 能量评分是该星球的重要内容分级指标，务必准确提取，过滤不可遗漏
- 星球地址和 ID 固定，无需用户指定
- **此 skill 只负责抓取和过滤，不做总结**；需要浓缩总结请使用 `zsxq-analyse` skill
- 如果用户提供的 token 过期，提示用户重新从浏览器 Cookie 中获取
- **每次调用必须重新从 API 拉取，不使用已有文件作为缓存**，同一天内多次调用也必须先删除旧文件再重新抓取