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
import re
import sys
import time
import shutil
import tempfile
import argparse
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import urllib.request
import urllib.error
import urllib.parse

import websocket
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

GROK_WS = "wss://grok.com/ws/bot/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB，服务器单次返回上限
MAX_ATTACHMENT_BYTES = 2 * 1024 * 1024 * 1024
MAX_PAGES = 10000
_SECRET_RE = re.compile(
    r"(?i)\b(cookie|authorization|sso-rw|sso|token|password)\b"
    r"(?:['\"]|\s)*[:=](?:['\"]|\s)*\S+"
)
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]+)?")

CHROME_PROFILES = [
    os.path.expanduser("~/Library/Application Support/Google/Chrome/Default/Cookies"),
    os.path.expanduser("~/Library/Application Support/Google/Chrome/Profile 1/Cookies"),
    os.path.expanduser("~/Library/Application Support/Google/Chrome/Profile 2/Cookies"),
]


def log(msg):
    print(redact(msg), flush=True)


def redact(msg):
    """Drop header-like secrets and JWT-shaped values before anything is printed."""
    text = _SECRET_RE.sub(lambda m: m.group(1) + "=[redacted]", str(msg))
    text = _JWT_RE.sub("[redacted]", text)
    if len(text) > 300:
        text = text[:300] + "…"
    return text


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def mkdir_private(path):
    os.makedirs(path, exist_ok=True)
    if not os.path.islink(path):
        os.chmod(path, 0o700)


def restrict_tree(root):
    """Owner-only modes. Skip symlinks so a link cannot chmod a file outside the export."""
    if not root or not os.path.isdir(root) or os.path.islink(root):
        return
    os.chmod(root, 0o700)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        kept = []
        for name in dirnames:
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                continue
            os.chmod(path, 0o700)
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            os.chmod(path, 0o600)


def fmt_time(v):
    if v is None or v == "":
        return ""
    if isinstance(v, (int, float)):
        ms = v
        if 0 < ms < 1e12:
            ms *= 1000
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ms / 1000))
        except Exception:
            return str(v)
    s = str(v)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return s


def sanitize(s):
    cleaned = []
    for c in str(s):
        if c in '\\/:*?"<>|' or ord(c) < 32:
            cleaned.append("_")
        else:
            cleaned.append(c)
    name = "".join(cleaned).strip().strip(".")[:60]
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        return "bot"
    return name


def cookie_header(cookies):
    parts = []
    for key, value in cookies.items():
        if not isinstance(key, str) or not isinstance(value, str) or not value:
            continue
        if any(c in key or c in value for c in "\r\n\x00;"):
            continue
        parts.append(f"{key}={value}")
    return "; ".join(parts)


def path_segment(value):
    """One URL path segment. Encodes slashes so an id cannot retarget the request."""
    if value is None:
        return None
    text = str(value)
    if not text or any(ord(c) < 32 for c in text):
        return None
    return urllib.parse.quote(text, safe="-._~")


# ---------------- Cookie 解密 ----------------
def _pkcs7_unpad(plain):
    if not plain:
        return None
    pad = plain[-1]
    if not isinstance(pad, int) or pad < 1 or pad > 16 or len(plain) < pad:
        return None
    if plain[-pad:] != bytes([pad]) * pad:
        return None
    return plain[:-pad]


def _read_cookie_rows(db_path):
    """Copy the locked Chrome DB, read grok rows, then delete the copy before decrypting."""
    fd, tmp = tempfile.mkstemp(prefix="grok-export-cookies-", suffix=".sqlite")
    os.close(fd)
    os.chmod(tmp, 0o600)
    try:
        with open(db_path, "rb") as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst)
        os.chmod(tmp, 0o600)
        con = sqlite3.connect(f"file:{tmp}?mode=ro&immutable=1", uri=True)
        try:
            return con.execute(
                "SELECT host_key, name, encrypted_value FROM cookies "
                "WHERE host_key LIKE '%grok.com' OR host_key LIKE '%x.ai'"
            ).fetchall()
        finally:
            con.close()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _chrome_safe_storage_password():
    try:
        return subprocess.check_output(
            ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage", "-a", "Chrome"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return None


def decrypt_chrome_cookies(db_path):
    rows = _read_cookie_rows(db_path)
    pw = _chrome_safe_storage_password()
    if not pw:
        return {}
    try:
        key = hashlib.pbkdf2_hmac("sha1", pw.encode(), b"saltysalt", 1003, 16)
        iv = b" " * 16

        def decrypt(blob):
            if not blob or blob[:3] != b"v10":
                return None
            c = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
            plain = _pkcs7_unpad(c.update(blob[3:]) + c.finalize())
            if not plain or len(plain) <= 32:
                return None
            return plain[32:].decode("utf-8", errors="replace")

        cookies = OrderedDict()
        for _host, name, blob in rows:
            if not isinstance(name, str) or not name:
                continue
            try:
                value = decrypt(blob)
            except Exception:
                value = None
            if isinstance(value, str) and value:
                cookies[name] = value
        return cookies
    finally:
        pw = None


def load_cookies():
    saw_db = False
    for db in CHROME_PROFILES:
        if not os.path.isfile(db):
            continue
        saw_db = True
        try:
            cookies = decrypt_chrome_cookies(db)
        except Exception as exc:
            log(f"读取 Chrome cookie 数据库失败：{redact(exc)}")
            continue
        if cookies.get("sso") and cookies.get("sso-rw"):
            return cookies
    if not saw_db:
        log("未找到 Chrome 的 Default、Profile 1 或 Profile 2 Cookies 文件")
    log("✗ 未能从 Chrome 解密出 grok.com 登录态")
    sys.exit(1)


# ---------------- WebSocket 客户端 ----------------
class BotClient:
    def __init__(self, cookies):
        self.cookie_header = cookie_header(cookies)
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
            raw = self.ws.recv()
            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, TypeError, UnicodeError):
                raise RuntimeError("websocket response was not JSON") from None
            if isinstance(msg, dict) and msg.get("id") == mid:
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


def download_attachment(client, agent_id, remote_path, local_path):
    """Stream to a sibling temp file and keep it only when the byte count matches."""
    head = client.read_attachment_chunk(agent_id, remote_path, 0, 1)
    if not isinstance(head, dict):
        return False
    try:
        total = int(head.get("totalSize") or 0)
    except (TypeError, ValueError):
        return False
    if total <= 0:
        return False
    if total > MAX_ATTACHMENT_BYTES:
        log("   附件超过 2GB，已跳过")
        return False
    partial = local_path + ".partial"
    if os.path.islink(local_path) or os.path.islink(partial):
        return False
    offset = 0
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(partial, flags, 0o600)
        with os.fdopen(fd, "wb") as handle:
            while offset < total:
                length = min(CHUNK_SIZE, total - offset)
                chunk = client.read_attachment_chunk(agent_id, remote_path, offset, length)
                if not isinstance(chunk, dict):
                    return False
                b64 = chunk.get("bytesBase64") or ""
                if not b64:
                    return False
                try:
                    piece = base64.b64decode(b64)
                except Exception:
                    return False
                if not piece:
                    return False
                handle.write(piece)
                offset += len(piece)
                if offset > MAX_ATTACHMENT_BYTES:
                    return False
        if offset != total:
            return False
        os.replace(partial, local_path)
        if not os.path.islink(local_path):
            os.chmod(local_path, 0o600)
        return True
    finally:
        if os.path.lexists(partial) and not os.path.islink(partial):
            try:
                os.remove(partial)
            except OSError:
                pass


# ---------------- 消息归一化 ----------------
def decode_body(entry):
    try:
        return json.loads(base64.b64decode(entry["body"]))
    except Exception:
        return None


def send_message_content(m):
    if not isinstance(m, dict):
        return ""
    mtype = m.get("type")
    if mtype == "text":
        return m.get("content") or ""
    if mtype == "widget":
        w = m.get("widget") if isinstance(m.get("widget"), dict) else {}
        parts = [w.get("prompt") or ""]
        options = w.get("options") if isinstance(w.get("options"), list) else []
        opts = [o.get("label") for o in options if isinstance(o, dict) and o.get("label")]
        if opts:
            parts.append("选项：" + " / ".join(opts))
        return "\n".join(p for p in parts if p)
    if mtype == "cursor-agent":
        return f"[cursor-agent] {m.get('title') or ''}"
    if mtype == "attachment":
        a = m.get("attachment") if isinstance(m.get("attachment"), dict) else {}
        return f"[附件] {a.get('file_name') or ''}"
    return json.dumps(m, ensure_ascii=False)


def normalize_entry(entry, body):
    if not isinstance(entry, dict):
        entry = {}
    if not isinstance(body, dict):
        body = None
    ek = entry.get("entryKind")
    ts = body.get("timestampMs") if body else None
    msg = {
        "seq": safe_int(entry.get("seq"), 0),
        "type": ek,
        "timestamp": fmt_time(ts),
        "timestampMs": ts,
        "entryId": entry.get("entryId"),
    }
    if body is None:
        msg["raw"] = None
        return msg
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
        m = body.get("message") if isinstance(body.get("message"), dict) else {}
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
            if isinstance(path, str) and path:
                out.append((agent_id, path, a.get("fileName"), m))
        elif m.get("type") == "send-message" and m.get("attachment"):
            a = m.get("attachment") or {}
            url = a.get("url") or ""
            if isinstance(url, str) and url.startswith("file://"):
                out.append((agent_id, url[len("file://"):], a.get("fileName"), m))
    return out


# ---------------- 并行附件下载 ----------------
_dl_lock = threading.Lock()
_dl_done = {"n": 0, "total": 0}


def download_one(args):
    cookies, agent_id, path, _fname, local_path = args
    client = BotClient(cookies)
    try:
        client.connect()
        return local_path, download_attachment(client, agent_id, path, local_path)
    except Exception as exc:
        log(f"   附件下载失败：{redact(exc)}")
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


# ---------------- 普通 Grok 对话导出（/rest/app-chat/*） ----------------
class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse a redirect that would send the session cookie off grok.com."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = urllib.parse.urlparse(newurl)
        old = urllib.parse.urlparse(req.full_url)
        if new.scheme != "https" or (new.hostname or "").lower() != (old.hostname or "").lower():
            raise urllib.error.HTTPError(req.full_url, code, "redirect off grok.com rejected", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_SameHostRedirect)


def chat_api(header, path, method="GET", body=None, tries=5):
    if not path.startswith("/") or path.startswith("//") or "\n" in path or "\r" in path:
        return 0, "bad path"
    url = "https://grok.com" + path
    data = json.dumps(body).encode() if body is not None else None
    for i in range(tries):
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Cookie": header, "User-Agent": UA, "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "https://grok.com", "Referer": "https://grok.com/",
        })
        try:
            with _OPENER.open(req, timeout=60) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            code = e.code
            try:
                e.read()
            except Exception:
                pass
            if (code == 429 or code >= 500) and i < tries - 1:
                time.sleep(1 * (2 ** i))
                continue
            return code, ""
        except Exception as e:
            if i < tries - 1:
                time.sleep(1 * (2 ** i))
                continue
            return 0, redact(e)
    return 0, "重试耗尽"


def _load_json(text):
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def export_chat(cookies, out_dir):
    os.umask(0o077)
    header = cookie_header(cookies)
    out_dir = os.path.expanduser(out_dir)
    mkdir_private(out_dir)
    conv_dir = os.path.join(out_dir, "conversations")
    mkdir_private(conv_dir)

    try:
        _export_chat_pages(header, out_dir, conv_dir)
    finally:
        restrict_tree(out_dir)


def _export_chat_pages(header, out_dir, conv_dir):
    log("拉取普通对话会话列表 ...")
    conversations = []
    cursor = None
    seen_cursors = set()
    pages = 0
    while pages < MAX_PAGES:
        pages += 1
        q = "?pageSize=200&limit=200"
        if cursor:
            q += "&nextCursor=" + urllib.parse.quote(str(cursor), safe="")
        st, body = chat_api(header, "/rest/app-chat/conversations" + q)
        if st != 200:
            log(f"⚠️ 会话列表请求失败（HTTP {st}）")
            break
        data = _load_json(body)
        if data is None:
            log(f"⚠️ 会话列表不是 JSON（HTTP {st}）")
            break
        arr = data.get("conversations") or []
        if not isinstance(arr, list):
            break
        conversations.extend(item for item in arr if isinstance(item, dict))
        nc = data.get("nextCursor")
        if not arr or not nc or nc in seen_cursors:
            break
        seen_cursors.add(nc)
        cursor = nc
    log(f"✓ 找到 {len(conversations)} 个普通会话")

    index = [f"# Grok 普通对话导出索引\n\n共 {len(conversations)} 个会话\n"]
    all_norm = []

    for i, conv in enumerate(conversations):
        cid = path_segment(conv.get("conversationId"))
        title = conv.get("title") or "未命名对话"
        if not isinstance(title, str):
            title = "未命名对话"
        n = f"{i + 1:04d}"
        safe = sanitize(title)
        label = title.replace("[", "").replace("]", "")

        messages = []
        if not cid:
            log(f"  ⚠️ 跳过缺少会话 id 的记录")
        else:
            try:
                st, body = chat_api(header,
                                    f"/rest/app-chat/conversations/{cid}/response-node?includeThreads=true")
                if st == 200:
                    payload = _load_json(body) or {}
                    nodes = payload.get("responseNodes") or []
                    if not isinstance(nodes, list):
                        nodes = []
                    ids = [x.get("responseId") for x in nodes if isinstance(x, dict) and x.get("responseId")]
                    for j in range(0, len(ids), 50):
                        st2, body2 = chat_api(
                            header,
                            f"/rest/app-chat/conversations/{cid}/load-responses",
                            "POST", {"responseIds": ids[j:j + 50]})
                        if st2 == 200:
                            page = _load_json(body2) or {}
                            got = page.get("responses") or []
                            if isinstance(got, list):
                                messages.extend(item for item in got if isinstance(item, dict))
                        time.sleep(0.05)
            except Exception as e:
                log(f"  ⚠️ 会话拉取失败: {redact(e)}")

        log(f"[{i + 1}/{len(conversations)}] {title}: {len(messages)} 条消息")

        norm = []
        for m in messages:
            sender = (m.get("sender") or "").lower()
            role = "user" if sender == "human" else "assistant"
            raw_msg = m.get("message")
            content = raw_msg if isinstance(raw_msg, str) else json.dumps(raw_msg or "", ensure_ascii=False)
            norm.append({
                "conversationId": conv.get("conversationId"),
                "title": title,
                "role": role,
                "sender": m.get("sender"),
                "content": content,
                "timestamp": fmt_time(m.get("createTime")),
                "timestampMs": m.get("createTime"),
            })
            all_norm.append(norm[-1])

        md = [f"# {title}", "", f"- 会话 ID: `{conv.get('conversationId', '')}`", f"- 消息数: {len(messages)}", "", "---", ""]
        for m in norm:
            who = "👤 用户" if m["role"] == "user" else "🤖 Grok"
            md += [f"## {who}", f"*{m['timestamp']}*", "", m["content"], "", "---", ""]
        with open(os.path.join(conv_dir, f"{n}_{safe}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        with open(os.path.join(conv_dir, f"{n}_{safe}.json"), "w", encoding="utf-8") as f:
            json.dump({"conversationId": conv.get("conversationId"), "title": title,
                       "createTime": conv.get("createTime"), "modifyTime": conv.get("modifyTime"),
                       "messages": messages}, f, ensure_ascii=False, indent=2)
        index.append(f"- [{n} {label}](conversations/{n}_{safe}.md) —— {len(messages)} 条")

    with open(os.path.join(out_dir, "_index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")
    with open(os.path.join(out_dir, "conversations.jsonl"), "w", encoding="utf-8") as f:
        for m in all_norm:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    log(f"✓ 普通对话导出完成：{len(conversations)} 个会话")


# ---------------- 主流程 ----------------
def _transcript_entries(client, agent_id):
    entries = []
    cursor = None
    seen = set()
    for _ in range(MAX_PAGES):
        result = client.transcript(agent_id, cursor)
        if not isinstance(result, dict):
            break
        batch = result.get("entries") or []
        if not isinstance(batch, list) or not batch:
            break
        entries.extend(item for item in batch if isinstance(item, dict))
        nc = result.get("nextCursor")
        if not nc or nc in seen:
            break
        seen.add(nc)
        cursor = nc
    entries.sort(key=lambda e: safe_int(e.get("seq"), 0))
    return entries


def _reconnect(cookies, client):
    client.close()
    fresh = BotClient(cookies)
    try:
        fresh.connect()
    except Exception:
        fresh.close()
        raise
    return fresh


def export_bots(cookies, out_dir, skip_attachments=False, workers=6):
    os.umask(0o077)
    out_dir = os.path.expanduser(out_dir)
    mkdir_private(out_dir)
    try:
        _export_bots_inner(cookies, out_dir, skip_attachments, workers)
    finally:
        restrict_tree(out_dir)


def _export_bots_inner(cookies, out_dir, skip_attachments, workers):
    log("=" * 60)
    log("Grok Bot 全量导出")
    log("=" * 60)

    client = BotClient(cookies)
    try:
        client.connect()
    except Exception as exc:
        log(f"连接 grok.com 失败：{redact(exc)}")
        client.close()
        return
    try:
        roster = client.roster()
    except Exception as exc:
        log(f"读取 bot 名单失败：{redact(exc)}")
        client.close()
        return
    agents = roster if isinstance(roster, list) else []
    agents = [a for a in agents if isinstance(a, dict)]
    log(f"✓ 找到 {len(agents)} 个 bot")

    index = [f"# Grok Bot 导出索引\n\n共 {len(agents)} 个 bot\n"]
    all_jobs = []

    for i, agent in enumerate(agents):
        aid = agent.get("agentId")
        name = agent.get("name") or "未命名 bot"
        if not isinstance(name, str):
            name = "未命名 bot"
        n = f"{i + 1:02d}"
        safe = sanitize(name)
        label = name.replace("[", "").replace("]", "")
        bot_dir = os.path.join(out_dir, f"{n}_{safe}")
        att_dir = os.path.join(bot_dir, "attachments")
        mkdir_private(bot_dir)
        mkdir_private(att_dir)
        try:
            entries = _transcript_entries(client, aid)
        except Exception as exc:
            log(f"[{i + 1}/{len(agents)}] {name}: 跳过（{redact(exc)}）")
            try:
                client = _reconnect(cookies, client)
            except Exception as reconn:
                log(f"重新连接失败：{redact(reconn)}")
                break
            continue
        log(f"[{i + 1}/{len(agents)}] {name}: {len(entries)} 条消息 ✓")

        decoded = []
        messages = []
        for e in entries:
            body = decode_body(e)
            decoded.append({"seq": e.get("seq"), "entryKind": e.get("entryKind"),
                            "entryId": e.get("entryId"), "body": body})
            messages.append(normalize_entry(e, body))

        atts = collect_attachments(messages, aid)
        used_names = set()
        for (a, path, fname, msg) in atts:
            base = f"{safe_int(msg.get('seq')):04d}_{sanitize(fname or 'file')}"
            local_name = base
            suffix = 2
            while local_name in used_names:
                local_name = f"{base}_{suffix}"
                suffix += 1
            used_names.add(local_name)
            local_path = os.path.join(att_dir, local_name)
            msg["localFile"] = f"attachments/{local_name}"
            if not (os.path.isfile(local_path) and not os.path.islink(local_path)
                    and os.path.getsize(local_path) > 0):
                all_jobs.append((a, path, fname, local_path))
        if atts:
            log(f"   📎 {len(atts)} 个附件")

        with open(os.path.join(bot_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(agent, f, ensure_ascii=False, indent=2)
        with open(os.path.join(bot_dir, "transcript.json"), "w", encoding="utf-8") as f:
            json.dump({"agent": agent, "entries": decoded}, f, ensure_ascii=False, indent=2)
        with open(os.path.join(bot_dir, "messages.jsonl"), "w", encoding="utf-8") as f:
            for m in messages:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
        with open(os.path.join(bot_dir, "conversation.md"), "w", encoding="utf-8") as f:
            f.write(render_conversation(messages, agent))

        index.append(f"- [{n} {label}]({n}_{safe}/conversation.md) —— {len(entries)} 条")

    client.close()

    if all_jobs and not skip_attachments:
        log(f"\n📥 开始并行下载 {len(all_jobs)} 个附件（{workers} 线程，4MB 分块）...")
        t0 = time.time()
        ok = download_all_parallel(all_jobs, cookies, workers)
        log(f"✓ 附件下载完成：{ok}/{len(all_jobs)} 成功，耗时 {time.time() - t0:.1f}s")
    elif all_jobs:
        log(f"\n已跳过附件下载（--skip-attachments），{len(all_jobs)} 个附件未下载")

    names = ", ".join(str(a.get("name") or "") for a in agents)
    agents_md = AGENTS_MD.replace("{count}", str(len(agents))).replace("{bots}", names)
    with open(os.path.join(out_dir, "roster.json"), "w", encoding="utf-8") as f:
        json.dump({"agents": agents}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "_index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")
    with open(os.path.join(out_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
        f.write(agents_md)

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


def main():
    ap = argparse.ArgumentParser(description="导出 grok.com 的 Grok Bot 和普通对话数据")
    ap.add_argument("out_dir", nargs="?", default=None,
                    help="输出目录（默认 ~/Downloads/grok-*-export-YYYYMMDD）")
    ap.add_argument("--mode", choices=["bot", "chat", "all"], default="bot",
                    help="bot=Grok Bot，chat=普通对话，all=两者都导（默认 bot）")
    ap.add_argument("--skip-attachments", "--messages-only", action="store_true",
                    dest="skip_attachments", help="只导出对话消息（秒出），不下载附件")
    ap.add_argument("--workers", type=int, default=6, help="附件并行下载线程数（1–32）")
    args = ap.parse_args()
    if args.workers < 1 or args.workers > 32:
        ap.error("--workers must be between 1 and 32")
    os.umask(0o077)

    cookies = load_cookies()
    stamp = time.strftime("%Y%m%d")

    if args.mode in ("bot", "all"):
        bot_dir = args.out_dir or os.path.expanduser(f"~/Downloads/grok-bot-export-{stamp}")
        export_bots(cookies, bot_dir, args.skip_attachments, args.workers)

    if args.mode in ("chat", "all"):
        if args.mode == "all" and args.out_dir:
            chat_dir = os.path.expanduser(args.out_dir) + "-chat"
        else:
            chat_dir = args.out_dir or os.path.expanduser(f"~/Downloads/grok-chat-export-{stamp}")
        log("=" * 60)
        log("Grok 普通对话导出")
        log("=" * 60)
        export_chat(cookies, chat_dir)


if __name__ == "__main__":
    main()
