---
name: Grok Export
description: Export complete Grok Bot data from grok.com (conversations + multimodal attachments) and query it for context. Use when the user wants to back up, export, or reference their Grok Bot data — including Chinese prompts like 导出/备份 Grok Bot 数据, or specific bot names (法律顾问, Coding任务管家, etc.).
---

# Grok Export

Export all Grok Bot data under a grok.com account (conversations + attachments) and query it for context.

## When to use

- User wants to export or back up their Grok Bot data, or their regular Grok chats.
- User wants to reference or recover context from their Grok Bots.
- User mentions "Grok Bot", "grok bot 数据", "导出", "备份", or a specific bot name.

## Workflow

### 1. Export data

Run from the repository root (the script is `grok-bot-export.py` there):

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

Requirements: macOS + Google Chrome logged into grok.com (profile Default, Profile 1, or Profile 2), `pip install -r requirements.txt`. The first run needs Keychain access to Chrome Safe Storage.

### 2. Query the exported data

Preferred: call the `grok-bot` MCP server (if configured) — structured and context-safe:

- `list_bots` — list every bot (name, agentId, message count, last active).
- `get_bot` — read a bot's full context; pass `limit` to cap messages (default 200).
- `search` — keyword search across all bots with surrounding context.

Fallback (read files directly):

- `AGENTS.md` — overall structure.
- `<NN_<bot>/>/messages.jsonl` — normalized message stream (one JSON per line).
- `<NN_<bot>/>/conversation.md` — readable, role-labeled dialogue.
- `<NN_<bot>/>/attachments/` — downloaded images/videos/files.

## Output schema (messages.jsonl)

Each line is one JSON message: `seq`, `type` (message / send-message / user-attachment / event / voice-call), `role` (user / assistant), `content`, `timestamp`, `attachment`, `localFile`, `event`, `call`.

## Notes

- Bot history is read over grok.com's bot WebSocket. Regular chats are read over the app-chat HTTP API, which can return HTTP 429 and is retried. The tool does not send new chat messages and does not delete data.
- MCP queries a Bot export only. Read a chat export from `_index.md` and `conversations/`.
- Prefer `get_bot` / `search` over pasting whole Bot files into the prompt.
