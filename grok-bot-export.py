#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grok Bot 全量数据导出工具（本地版，无需浏览器插件）

完整导出账号下所有 Grok Bot 的数据，包括全部对话消息和多模态附件（图片/视频/文件）。

速度优化：
  - 消息数据秒出（transcript 分页拉取很快）
  - 附件用 4MB 大分块（服务器单次上限）+ 多线程并行下载

原理：
  1. 从本机 Chrome cookie 数据库解密出 grok.com 登录态
  2. 连接 wss://grok.com/ws/bot/（JSON-RPC over WebSocket）
  3. bot.roster 列出所有 bot → bot.transcript.offbox 分页拉历史
  4. 附件用 bot.command(readAttachmentChunk) 分块下载（4MB/块，多线程）

用法：
  python3 grok-bot-export.py [输出目录] [--skip-attachments] [--workers N]
"""

import sqlite3
import hashlib
import subprocess
import json
import base64
import os
import sys
import time
import shutil
import tempfile
import argparse
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

import websocket
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

GROK_WS = "wss://grok.com/ws/bot/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB，服务器单次返回上限

CHROME_PROFILES = [
    os.path.expanduser("~/Library/Application Support/Google/Chrome/Default/Cookies"),
    os.path.expanduser("~/Library/Application Support/Google/Chrome/Profile 1/Cookies"),
    os.path.expanduser("~/Library/Application Support/Google/Chrome/Profile 2/Cookies"),
]


def log(msg):
    print(msg, flush=True)


def fmt_time(ms):
    if not ms:
        return ""
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ms / 1000))
    except Exception:
        return str(ms)


def sanitize(s):
    return "".join(c if c not in '\\/:*?"<>|\n\r\t' else "_" for c in str(s)).strip()[:60] or "bot"


# ---------------- Cookie 解密 ----------------
def decrypt_chrome_cookies(db_path):
    try:
        pw = subprocess.check_output(
            ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage", "-a", "Chrome"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        pw = None

    tmp = os.path.join(tempfile.gettempdir(), f"chrome_cookies_{os.getpid()}.sqlite")
    shutil.copy2(db_path, tmp)
    con = sqlite3.connect(f"file:{tmp}?mode=ro&immutable=1", uri=True)
    rows = con.execute(
        "SELECT host_key, name, encrypted_value FROM cookies "
        "WHERE host_key LIKE '%grok.com' OR host_key LIKE '%x.ai'"
    ).fetchall()
    con.close()
    try:
        os.remove(tmp)
    except Exception:
        pass

    if not pw:
        return {}
    key = hashlib.pbkdf2_hmac("sha1", pw.encode(), b"saltysalt", 1003, 16)
    iv = b" " * 16

    def decrypt(blob):
        if blob[:3] != b"v10":
            return None
        data = blob[3:]
        c = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        plain = c.update(data) + c.finalize()
        pad = plain[-1]
        return plain[:-pad][32:].decode("utf-8", errors="replace")

    cookies = OrderedDict()
    for host, name, blob in rows:
        try:
            cookies[name] = decrypt(blob)
        except Exception:
            pass
    return cookies


def load_cookies():
    for db in CHROME_PROFILES:
        if not os.path.exists(db):
            continue
        cookies = decrypt_chrome_cookies(db)
        if cookies.get("sso") and cookies.get("sso-rw"):
            return cookies
    log("✗ 未能从 Chrome 解密出 grok.com 登录态")
    sys.exit(1)


# ---------------- WebSocket 客户端 ----------------
class BotClient:
    def __init__(self, cookies):
        self.cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        self.ws = None
        self._id = 0

    def connect(self):
        self.ws = websocket.create_connection(
            GROK_WS,
            header=[f"Cookie: {self.cookie_header}", f"User-Agent: {UA}",
                    "Origin: https://grok.com"],
            timeout=120,
        )
        self.ws.send(json.dumps({"protocol_version": "1.0.0", "kind": "bot_client", "capabilities": []}))
        self.ws.recv()

    def call(self, method, params):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                return msg

    def roster(self):
        return (self.call("bot.roster", {}).get("result") or {}).get("agents", [])

    def transcript(self, agent_id, cursor=None):
        params = {"agentId": agent_id}
        if cursor:
            params["cursor"] = cursor
        return self.call("bot.transcript.offbox", params).get("result") or {}

    def read_attachment_chunk(self, agent_id, path, offset, length):
        r = self.call("bot.command", {
            "agentId": agent_id,
            "name": "readAttachmentChunk",
            "args": {"path": path, "offset": offset, "length": length},
        })
        return r.get("result") or {}

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def download_attachment(client, agent_id, path):
    head = client.read_attachment_chunk(agent_id, path, 0, 1)
    total = int(head.get("totalSize") or 0)
    mime = head.get("mime") or ""
    if total <= 0:
        return None, None
    data = bytearray()
    offset = 0
    while offset < total:
        chunk = client.read_attachment_chunk(agent_id, path, offset, CHUNK_SIZE)
        b64 = chunk.get("bytesBase64") or ""
        if b64:
            data.extend(base64.b64decode(b64))
        offset += CHUNK_SIZE
    return bytes(data), mime


# ---------------- 消息归一化 ----------------
def decode_body(entry):
    try:
        return json.loads(base64.b64decode(entry["body"]))
    except Exception:
        return None


def send_message_content(m):
    mtype = m.get("type")
    if mtype == "text":
        return m.get("content") or ""
    if mtype == "widget":
        w = m.get("widget") or {}
        parts = [w.get("prompt") or ""]
        opts = [o.get("label") for o in (w.get("options") or []) if o.get("label")]
        if opts:
            parts.append("选项：" + " / ".join(opts))
        return "\n".join(p for p in parts if p)
    if mtype == "cursor-agent":
        return f"[cursor-agent] {m.get('title') or ''}"
    if mtype == "attachment":
        a = m.get("attachment") or {}
        return f"[附件] {a.get('file_name') or ''}"
    return json.dumps(m, ensure_ascii=False)


def normalize_entry(entry, body):
    ek = entry.get("entryKind")
    ts = body.get("timestampMs") if body else None
    msg = {
        "seq": int(entry.get("seq") or 0),
        "type": ek,
        "timestamp": fmt_time(ts),
        "timestampMs": ts,
        "entryId": entry.get("entryId"),
    }
    if ek == "message":
        role = (body.get("role") or "").lower()
        msg["role"] = role
        content = body.get("content") or ""
        if not content and body.get("richText"):
            content = json.dumps(body.get("richText"), ensure_ascii=False)
        msg["content"] = content
        if body.get("fromAgent"):
            msg["fromAgent"] = body["fromAgent"]
        if body.get("replyTo"):
            msg["replyTo"] = body["replyTo"]
    elif ek == "send-message":
        m = body.get("message") or {}
        msg["role"] = "assistant"
        msg["messageType"] = m.get("type")
        msg["content"] = send_message_content(m)
        if m.get("type") == "attachment":
            msg["attachment"] = {"fileName": m.get("file_name"),
                                 "url": m.get("url"), "sourcePath": m.get("source_path")}
    elif ek == "user-attachment":
        msg["role"] = "user"
        msg["content"] = ""
        msg["attachment"] = {
            "fileName": body.get("file_name"),
            "filePath": body.get("file_path"),
            "byteSize": body.get("byteSize"),
            "width": body.get("width"),
            "height": body.get("height"),
        }
    elif ek == "event":
        msg["event"] = body.get("event")
    elif ek == "voice-call":
        msg["call"] = body.get("call")
    else:
        msg["raw"] = body
    return msg


ROLE_LABEL = {"user": "👤 用户", "assistant": "🤖 Bot", "system": "⚙️ 系统"}


def render_conversation(messages, agent):
    name = agent.get("name") or "未命名 bot"
    lines = [f"# {name}", ""]
    lines.append(f"- Bot ID: `{agent.get('agentId', '')}`")
    lines.append(f"- 消息数: {len(messages)}")
    if agent.get("lastTurnAt"):
        lines.append(f"- 最后活跃: {fmt_time(agent['lastTurnAt'])}")
    lines += ["", "---", ""]
    for m in messages:
        t = m.get("timestamp") or ""
        mt = m.get("type")
        if mt == "message":
            who = ROLE_LABEL.get(m.get("role"), "🤖 Bot")
            tag = ""
            if m.get("fromAgent") and m.get("role") != "user":
                tag = f"（来自 {m['fromAgent'].get('name', 'agent')}）"
            lines.append(f"## {who}{tag}")
            lines.append(f"*{t}*")
            lines.append("")
            lines.append(m.get("content") or "")
            lines.append("")
        elif mt == "send-message":
            lines.append("## 🤖 Bot")
            lines.append(f"*{t}*")
            lines.append("")
            if m.get("attachment") and not m.get("content", "").startswith("["):
                a = m["attachment"]
                lines.append(f"📎 附件：{a.get('fileName') or ''}")
                if m.get("localFile"):
                    lines.append(f"`{m['localFile']}`")
            else:
                lines.append(m.get("content") or "")
            lines.append("")
        elif mt == "user-attachment":
            a = m.get("attachment") or {}
            nm = a.get("fileName") or a.get("filePath") or "附件"
            extra = []
            if a.get("byteSize"):
                extra.append(f"{a['byteSize']} 字节")
            info = f"（{', '.join(extra)}）" if extra else ""
            lines.append(f"## 📎 附件：{nm}")
            lines.append(f"*{t}* {info}")
            if m.get("localFile"):
                lines.append(f"`{m['localFile']}`")
            lines.append("")
        elif mt == "event":
            lines.append("## ⚡ 事件")
            lines.append(f"*{t}*")
            lines.append("")
            lines.append(json.dumps(m.get("event"), ensure_ascii=False) if m.get("event") else "")
            lines.append("")
        elif mt == "voice-call":
            lines.append("## 📞 通话")
            lines.append(f"*{t}*")
            lines.append("")
            lines.append(json.dumps(m.get("call"), ensure_ascii=False) if m.get("call") else "")
            lines.append("")
        else:
            lines.append(f"## [{mt}]")
            lines.append(f"*{t}*")
            lines.append("")
            lines.append(json.dumps(m.get("raw") or {}, ensure_ascii=False))
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def collect_attachments(messages, agent_id):
    """收集需下载的附件，返回 [ (agent_id, path, fileName) ]。"""
    out = []
    for m in messages:
        if m.get("type") == "user-attachment":
            a = m.get("attachment") or {}
            path = a.get("filePath")
            if path:
                out.append((agent_id, path, a.get("fileName"), m.get("seq")))
        elif m.get("type") == "send-message" and m.get("attachment"):
            a = m.get("attachment") or {}
            url = a.get("url") or ""
            if url.startswith("file://"):
                out.append((agent_id, url[len("file://"):], a.get("fileName"), m.get("seq")))
    return out


# ---------------- 并行附件下载 ----------------
_dl_lock = threading.Lock()
_dl_done = {"n": 0, "total": 0}


def download_one(args):
    cookies, agent_id, path, fname, local_path = args
    client = BotClient(cookies)
    try:
        client.connect()
        data, mime = download_attachment(client, agent_id, path)
        if data:
            with open(local_path, "wb") as f:
                f.write(data)
        return local_path, bool(data)
    except Exception:
        return local_path, False
    finally:
        client.close()
        with _dl_lock:
            _dl_done["n"] += 1
            n, total = _dl_done["n"], _dl_done["total"]
            if n % 5 == 0 or n == total:
                log(f"   📥 附件下载进度 {n}/{total}")


def download_all_parallel(jobs, cookies, workers):
    """jobs: [ (agent_id, path, fname, local_path) ]"""
    _dl_done["total"] = len(jobs)
    _dl_done["n"] = 0
    todo = [(cookies, a, p, f, lp) for (a, p, f, lp) in jobs]
    ok = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(download_one, t) for t in todo]
        for f in as_completed(futures):
            lp, success = f.result()
            if success:
                ok += 1
    return ok


# ---------------- 主流程 ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", nargs="?", default=os.path.expanduser(
        "~/Downloads/grok-bot-export-" + time.strftime("%Y%m%d")))
    ap.add_argument("--skip-attachments", "--messages-only", action="store_true",
                    dest="skip_attachments",
                    help="只导出对话消息（秒出），不下载附件")
    ap.add_argument("--workers", type=int, default=6, help="附件并行下载线程数")
    args = ap.parse_args()

    out_dir = os.path.expanduser(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    log("=" * 60)
    log("Grok Bot 全量导出")
    log("=" * 60)

    cookies = load_cookies()
    client = BotClient(cookies)
    client.connect()
    agents = client.roster()
    log(f"✓ 找到 {len(agents)} 个 bot")

    index = [f"# Grok Bot 导出索引\n\n共 {len(agents)} 个 bot\n"]
    all_jobs = []  # 待下载附件

    # ---- 阶段 1：拉消息（秒出）----
    for i, agent in enumerate(agents):
        aid = agent.get("agentId")
        name = agent.get("name") or "未命名 bot"
        n = f"{i + 1:02d}"
        safe = sanitize(name)
        bot_dir = os.path.join(out_dir, f"{n}_{safe}")
        att_dir = os.path.join(bot_dir, "attachments")
        os.makedirs(att_dir, exist_ok=True)

        entries = []
        cursor = None
        while True:
            result = client.transcript(aid, cursor)
            batch = result.get("entries", [])
            entries.extend(batch)
            nc = result.get("nextCursor")
            if not batch or not nc:
                break
            cursor = nc
        entries.sort(key=lambda e: int(e.get("seq") or 0))
        log(f"[{i + 1}/{len(agents)}] {name}: {len(entries)} 条消息 ✓")

        decoded = []
        messages = []
        for e in entries:
            body = decode_body(e)
            decoded.append({"seq": e.get("seq"), "entryKind": e.get("entryKind"),
                            "entryId": e.get("entryId"), "body": body})
            messages.append(normalize_entry(e, body))

        # 预设附件本地路径 + 收集下载任务
        atts = collect_attachments(messages, aid)
        for (a, path, fname, seq) in atts:
            local_name = f"{seq:04d}_{sanitize(fname or f'file_{seq}')}"
            local_path = os.path.join(att_dir, local_name)
            for m in messages:
                if m.get("seq") == seq and m.get("type") in ("user-attachment", "send-message"):
                    m["localFile"] = f"attachments/{local_name}"
            if not (os.path.exists(local_path) and os.path.getsize(local_path) > 0):
                all_jobs.append((a, path, fname, local_path))
        if atts:
            log(f"   📎 {len(atts)} 个附件")

        # 写文件（消息已秒出）
        with open(os.path.join(bot_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(agent, f, ensure_ascii=False, indent=2)
        with open(os.path.join(bot_dir, "transcript.json"), "w", encoding="utf-8") as f:
            json.dump({"agent": agent, "entries": decoded}, f, ensure_ascii=False, indent=2)
        with open(os.path.join(bot_dir, "messages.jsonl"), "w", encoding="utf-8") as f:
            for m in messages:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
        with open(os.path.join(bot_dir, "conversation.md"), "w", encoding="utf-8") as f:
            f.write(render_conversation(messages, agent))

        index.append(f"- [{n} {name}]({n}_{safe}/conversation.md) —— {len(entries)} 条")

    client.close()

    # ---- 阶段 2：并行下载附件 ----
    if all_jobs and not args.skip_attachments:
        log(f"\n📥 开始并行下载 {len(all_jobs)} 个附件（{args.workers} 线程，4MB 分块）...")
        t0 = time.time()
        ok = download_all_parallel(all_jobs, cookies, args.workers)
        log(f"✓ 附件下载完成：{ok}/{len(all_jobs)} 成功，耗时 {time.time() - t0:.1f}s")
    elif all_jobs:
        log(f"\n已跳过附件下载（--skip-attachments），{len(all_jobs)} 个附件未下载")

    with open(os.path.join(out_dir, "roster.json"), "w", encoding="utf-8") as f:
        json.dump({"agents": agents}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "_index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")
    with open(os.path.join(out_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
        f.write(AGENTS_MD.format(count=len(agents), bots=", ".join(a.get("name", "") for a in agents)))

    log("\n" + "=" * 60)
    log(f"✅ 完成！共 {len(agents)} 个 bot → {out_dir}")
    log("=" * 60)


AGENTS_MD = """# Grok Bot 数据导出（供 AI Agent 使用）

这是从 grok.com 导出的 Grok Bot 账号数据。共 {count} 个 bot：{bots}。

## 目录结构

- `AGENTS.md` —— 本文件（建议 Agent 先读）
- `_index.md` —— 所有 bot 索引
- `roster.json` —— 所有 bot 名单（机器可读）
- `NN_<bot名>/` —— 每个 bot 一个文件夹：
  - `meta.json` —— bot 元数据（name、agentId、status、lastTurnAt）
  - `messages.jsonl` —— 归一化消息流（每行一条，统一 schema，最适合喂给 AI/RAG）
  - `conversation.md` —— 按时间排序的可读对话
  - `transcript.json` —— 原始完整数据（保底）
  - `attachments/` —— 多模态文件（图片、视频等）

## messages.jsonl 字段说明

- `seq`：序号（按时间递增）
- `type`：消息类型（message / send-message / user-attachment / event / voice-call）
- `role`：角色（user=用户，assistant=bot）
- `content`：文本内容
- `timestamp` / `timestampMs`：时间
- `attachment`：附件信息（fileName、filePath、byteSize 等）
- `localFile`：附件本地相对路径（在 attachments/ 下）
- `event` / `call`：事件 / 通话原始数据
"""


if __name__ == "__main__":
    main()
