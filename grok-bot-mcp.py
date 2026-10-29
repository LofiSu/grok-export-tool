#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grok Bot 数据查询 MCP Server（轻量、零依赖、stdio 协议）

让 Codex / Claude Code / OpenCode / Grok Bot 等 Agent 能查询由
grok-bot-export.py 导出的 Grok Bot 数据。

提供的工具：
  1. list_bots           列出所有 bot（名称、ID、消息数、最后活跃时间）
  2. get_bot             获取某个 bot 的完整上下文（元数据 + 消息流）
  3. search              在全部 bot 消息里做关键词检索（含上下文）

配置方式（以 Claude Code / Codex 为例，JSON-RPC over stdio）：

  {
    "mcpServers": {
      "grok-bot": {
        "command": "python3",
        "args": ["/Users/sulin/grok-export-tool/grok-bot-mcp.py",
                 "/Users/sulin/Downloads/grok-bot-export-full-20261029"]
      }
    }
  }

依赖：无（仅 Python 标准库）
"""

import json
import os
import sys
import glob

DATA_DIR = None


def log_stderr(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


# ---------------- 数据读取 ----------------
def find_bot_folders():
    folders = []
    for p in sorted(glob.glob(os.path.join(DATA_DIR, "*"))):
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "meta.json")):
            folders.append(p)
    return folders


def load_bots_overview():
    bots = []
    for folder in find_bot_folders():
        meta_path = os.path.join(folder, "meta.json")
        msgs_path = os.path.join(folder, "messages.jsonl")
        try:
            meta = json.load(open(meta_path, encoding="utf-8"))
        except Exception:
            meta = {}
        msg_count = 0
        if os.path.exists(msgs_path):
            try:
                with open(msgs_path, encoding="utf-8") as f:
                    msg_count = sum(1 for _ in f)
            except Exception:
                pass
        bots.append({
            "folder": os.path.basename(folder),
            "name": meta.get("name", ""),
            "agentId": meta.get("agentId", ""),
            "status": meta.get("status", ""),
            "lastTurnAt": meta.get("lastTurnAt", 0),
            "messageCount": msg_count,
        })
    return bots


def find_bot_folder(name_or_index):
    bots = load_bots_overview()
    # 按序号
    for b in bots:
        if b["folder"].startswith(name_or_index):
            return b, b["folder"]
    # 按名字模糊
    for b in bots:
        if name_or_index in b["name"] or name_or_index in b["agentId"]:
            return b, b["folder"]
    return None, None


def load_messages(folder):
    msgs_path = os.path.join(DATA_DIR, folder, "messages.jsonl")
    if not os.path.exists(msgs_path):
        return []
    msgs = []
    with open(msgs_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    msgs.append(json.loads(line))
                except Exception:
                    pass
    return msgs


def fmt_ts(ms):
    if not ms:
        return ""
    import time
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ms / 1000))
    except Exception:
        return str(ms)


# ---------------- 工具实现 ----------------
def tool_list_bots():
    bots = load_bots_overview()
    if not bots:
        return "未找到导出的数据。请先运行 grok-bot-export.py，并确认数据目录正确。"
    lines = [f"共 {len(bots)} 个 bot："]
    for i, b in enumerate(bots):
        last = fmt_ts(b["lastTurnAt"]) if b.get("lastTurnAt") else "未知"
        lines.append(f"{i + 1}. {b['name']}（agentId: {b['agentId']}，{b['messageCount']} 条消息，最后活跃 {last}）")
    return "\n".join(lines)


def tool_get_bot(bot, limit=200):
    meta, folder = find_bot_folder(bot)
    if not folder:
        return f"未找到名为「{bot}」的 bot。请用 list_bots 查看可用的 bot。"
    msgs = load_messages(folder)
    limit = min(int(limit), len(msgs))
    lines = [f"# {meta['name']}", "", f"agentId: {meta['agentId']}", f"总消息数: {len(msgs)}",
             f"最后活跃: {fmt_ts(meta.get('lastTurnAt'))}", "", "---", ""]
    for m in msgs[:limit]:
        t = m.get("timestamp") or ""
        typ = m.get("type")
        role = m.get("role")
        if typ in ("message", "send-message"):
            who = "用户" if role == "user" else "Bot"
            lines.append(f"[{who}] {t}")
            lines.append(m.get("content") or "")
        elif typ == "user-attachment":
            a = m.get("attachment") or {}
            lines.append(f"[附件] {t}  {a.get('fileName') or ''}  {m.get('localFile') or ''}")
        elif typ == "event":
            lines.append(f"[事件] {t}  {json.dumps(m.get('event'), ensure_ascii=False)}")
        elif typ == "voice-call":
            lines.append(f"[通话] {t}  {json.dumps(m.get('call'), ensure_ascii=False)}")
        else:
            lines.append(f"[{typ}] {t}")
        lines.append("")
    if len(msgs) > limit:
        lines.append(f"...（仅显示前 {limit} 条，共 {len(msgs)} 条。可用更大的 limit 参数获取更多）")
    return "\n".join(lines)


def tool_search(query, context=2):
    query = query.strip()
    if not query:
        return "请输入搜索关键词。"
    results = []
    for folder in find_bot_folders():
        msgs = load_messages(folder)
        meta = {}
        try:
            meta = json.load(open(os.path.join(DATA_DIR, folder, "meta.json"), encoding="utf-8"))
        except Exception:
            pass
        hits = [i for i, m in enumerate(msgs) if query in (m.get("content") or "")]
        for i in hits:
            lo = max(0, i - int(context))
            hi = min(len(msgs), i + int(context) + 1)
            block = [f"### {meta.get('name', folder)}  (消息 {i + 1}/{len(msgs)})"]
            for j in range(lo, hi):
                m = msgs[j]
                who = "用户" if m.get("role") == "user" else "Bot"
                marker = " ← 命中" if j == i else ""
                block.append(f"[{who}] {m.get('timestamp') or ''}: {m.get('content') or '(附件)'}{marker}")
            results.append("\n".join(block))
            if len(results) >= 10:
                break
        if len(results) >= 10:
            break
    if not results:
        return f"未找到包含「{query}」的消息。"
    return f"找到 {len(results)} 处匹配：\n\n" + "\n\n".join(results)


TOOLS = {
    "list_bots": {
        "description": "列出所有 Grok Bot（名称、agentId、消息数、最后活跃时间）。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "get_bot": {
        "description": "获取某个 bot 的完整上下文（元数据 + 按时间排序的消息流）。参数 bot 为 bot 名称或序号，limit 为最多返回的消息条数（默认 200）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bot": {"type": "string", "description": "bot 名称或序号，如「法律顾问」或「05」"},
                "limit": {"type": "integer", "description": "最多返回的消息条数，默认 200"},
            },
            "required": ["bot"],
        },
    },
    "search": {
        "description": "在全部 bot 的消息里搜索关键词，返回命中的消息及其上下文。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "要搜索的关键词"},
                "context": {"type": "integer", "description": "每条命中前后包含的上下文消息条数，默认 2"},
            },
            "required": ["query"],
        },
    },
}


# ---------------- MCP 协议 ----------------
def send_rpc(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle_request(msg):
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": params.get("protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "grok-bot-mcp", "version": "1.0.0"},
        }}
    if method == "tools/list":
        tools = [{"name": n, "description": t["description"], "inputSchema": t["inputSchema"]}
                 for n, t in TOOLS.items()]
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": tools}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            if name == "list_bots":
                text = tool_list_bots()
            elif name == "get_bot":
                text = tool_get_bot(args.get("bot", ""), args.get("limit", 200))
            elif name == "search":
                text = tool_search(args.get("query", ""), args.get("context", 2))
            else:
                text = f"未知工具: {name}"
            return {"jsonrpc": "2.0", "id": mid,
                    "result": {"content": [{"type": "text", "text": text}], "isError": False}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid,
                    "result": {"content": [{"type": "text", "text": f"错误: {e}"}], "isError": True}}
    return None


def main():
    global DATA_DIR
    if len(sys.argv) > 1:
        DATA_DIR = os.path.expanduser(sys.argv[1])
    else:
        # 默认找最新的导出目录
        candidates = sorted(glob.glob(os.path.expanduser("~/Downloads/grok-bot-export-*")),
                            key=os.path.getmtime, reverse=True)
        DATA_DIR = candidates[0] if candidates else "."
    if not os.path.isdir(DATA_DIR):
        log_stderr(f"数据目录不存在: {DATA_DIR}")
    log_stderr(f"grok-bot-mcp 启动，数据目录: {DATA_DIR}")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if "id" not in msg:
            # 通知（如 notifications/initialized），忽略
            continue
        resp = handle_request(msg)
        if resp:
            send_rpc(resp)


if __name__ == "__main__":
    main()
