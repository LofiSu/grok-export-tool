---
name: Grok Export
description: Export complete Grok Bot data from grok.com (conversations + multimodal attachments) and query it for context. Use when the user wants to back up, export, or reference their Grok Bot data — including Chinese prompts like 导出/备份 Grok Bot 数据, or specific bot names (法律顾问, Coding任务管家, etc.).
---

# Grok Export

Export all Grok Bot data under a grok.com account (conversations + attachments) and query it for context.

## When to use

- User wants to export or back up their Grok Bot data.
- User wants to reference/recover context from their Grok Bots.
- User mentions "Grok Bot", "grok bot 数据", "导出", "备份", or a specific bot name.

## Workflow

### 1. Export data

The export script lives at the repo root (`../../grok-bot-export.py` relative to this skill):

```bash
# Grok Bots (default): full export (conversations + attachments, idempotent)
python3 ../../grok-bot-export.py

# Grok Bots: messages only (~20 s, no attachments)
python3 ../../grok-bot-export.py --messages-only

# Regular Grok chats (non-Bot conversations)
python3 ../../grok-bot-export.py --mode chat
```

Output defaults to `~/Downloads/grok-bot-export-YYYYMMDD/`.

Requirements: Google Chrome logged into grok.com (macOS / Windows / Linux — see README for auth), `pip install -r requirements.txt`.

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

- The tool reads history over grok.com's internal WebSocket API using the cookies of an already-logged-in Chrome. It never sends messages, deletes, or modifies data, and is not affected by message quota.
- Always prefer `get_bot`/`search` (MCP) over reading raw files, to keep context bounded.
