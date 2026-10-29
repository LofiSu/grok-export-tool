---
name: grok-export
description: Export Grok Bots and regular Grok chats from grok.com into a local archive, then query Bot archives with the MCP server. Use for backup or lookup requests, including 导出/备份 Grok 数据, or a fictional bot name such as Example Bot.
license: MIT
compatibility: Requires Python 3.9+ and `pip install -r requirements.txt`. macOS can read Chrome cookies from the Keychain. Windows and Linux may need `--cookie "sso=...; sso-rw=..."`.
---

# Grok Export

Export Grok Bots (conversations and attachments) and regular Grok chats, then query the Bot archive.

## When to use

- User wants to export or back up Grok Bots or regular Grok chats.
- User wants to look something up in a Bot archive.
- User mentions "Grok Bot", "导出", or "备份".

## Workflow

### 1. Export data

Run from the repository root:

```bash
# Grok Bots (default): messages and attachments. Re-runs skip non-empty files.
python3 grok-bot-export.py

# Grok Bots: text only. Skips attachment downloads.
python3 grok-bot-export.py --messages-only

# Regular Grok chats (text and raw JSON, no attachment files)
python3 grok-bot-export.py --mode chat

# Both. Two directories.
python3 grok-bot-export.py --mode all
```

Bot output defaults to `~/Downloads/grok-bot-export-YYYYMMDD/`. Chat output defaults to `~/Downloads/grok-chat-export-YYYYMMDD/`. With `--mode all` and a directory argument, chats go to that path plus `-chat`.

On macOS the first run needs Keychain access to Chrome Safe Storage. On Windows or Linux, if automatic decryption fails, pass placeholders only in real use of your own session: `--cookie "sso=...; sso-rw=..."`. Do not paste those values into chat, issues, or git.

### 2. Query the exported data

Preferred for Bots: the `grok-bot` MCP server.

- `list_bots` — name, agentId, message count, last active.
- `get_bot` — one bot. `limit` defaults to 200.
- `search` — keyword search with neighboring lines.

The MCP server reads Bot folders only. Read a chat export from `_index.md` and `conversations/`.

Fallback for a Bot folder:

- `AGENTS.md`
- `messages.jsonl`
- `conversation.md`
- `attachments/`

## Output schema (messages.jsonl)

Each line is one JSON object: `seq`, `type` (message / send-message / user-attachment / event / voice-call), `role` (user / assistant), `content`, `timestamp`, `attachment`, `localFile`, `event`, `call`.

## Notes

- The tool reads history you already have. It does not send new chats and does not delete data.
- Bot history uses the bot WebSocket. Regular chats use grok.com's app-chat HTTP API, which can return HTTP 429 and is retried.
- Prefer `get_bot` / `search` over pasting whole Bot files into the prompt.
