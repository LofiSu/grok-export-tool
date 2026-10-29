# grok-export-tool

[English](README.md) · [中文](README.zh-CN.md)

Export your complete **Grok Bot** data from [grok.com](https://grok.com) — every conversation plus all multimodal attachments (images, videos, files) — into an **Agent-friendly** format, with a lightweight **MCP server** and **OpenCode skill** so AI assistants (Codex, Claude Code, OpenCode, …) can query the context directly.

> Fully local. No browser extension, no re-login, no API key, and **no message-quota dependency** — it reads history over grok.com's internal WebSocket API using the cookies from your already-logged-in Chrome.

## Features

- 📦 Exports every Grok Bot under your account (roster + full transcript)
- 🖼️ Downloads multimodal attachments (images / videos / files) in parallel, 4 MB chunks
- 🧠 Outputs an Agent-friendly structure (normalized JSONL + readable Markdown + raw JSON)
- 🔌 Lightweight, zero-dependency MCP server (`list_bots` / `get_bot` / `search`)

## Platform support

| Platform | Cookie auth |
| --- | --- |
| **macOS** | Auto-decrypts via the Keychain ("Chrome Safe Storage"). |
| **Windows** | Auto-decrypts via DPAPI (`pip install pywin32`); if Chrome uses App-Bound Encryption, use `--cookie`. |
| **Linux** | Best-effort (legacy "peanuts" key / plaintext); otherwise use `--cookie`. |

Universal fallback for any platform:

```bash
python3 grok-bot-export.py --cookie "sso=...; sso-rw=..."
```

(Copy the `sso` and `sso-rw` values from DevTools → Application → Cookies → grok.com.)

Requires Python 3.9+.

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Grok Bots (default): full export (messages + attachments)
python3 grok-bot-export.py

# Grok Bots: messages only (fast, ~20 s)
python3 grok-bot-export.py --messages-only

# Regular Grok chats (non-Bot conversations)
python3 grok-bot-export.py --mode chat

# Both Bots and regular chats
python3 grok-bot-export.py --mode all
```

Output goes to `~/Downloads/grok-bot-export-YYYYMMDD/` (or `~/Downloads/grok-chat-export-YYYYMMDD/` for chat mode) by default — pass a directory as the first argument to override. Attachment downloads are idempotent — already-downloaded files are skipped on re-runs.

## Output structure

```
grok-bot-export-YYYYMMDD/
  AGENTS.md               ← Agent instructions (read this first)
  _index.md               all-bot index
  roster.json             machine-readable bot list
  01_<bot name>/
    meta.json             bot metadata (name / agentId / status / lastTurnAt)
    transcript.json       raw complete data (fallback)
    messages.jsonl        ★ normalized message stream (one JSON per line)
    conversation.md       readable, role-labeled dialogue
    attachments/          multimodal files
```

`messages.jsonl` uses one uniform schema per line: `seq`, `type`, `role` (`user` / `assistant`), `content`, `timestamp`, `attachment`, `localFile`, `event`, `call`.

## MCP server

`grok-bot-mcp.py` is a stdio MCP server with zero runtime dependencies. Configure it to let an agent query the exported data:

```jsonc
// ~/.config/opencode/opencode.json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "grok-bot": {
        "type": "local",
        "command": ["python3", "/path/to/grok-bot-mcp.py", "/path/to/grok-bot-export-YYYYMMDD"]
      }
    }
  }
}
```

Tools: `list_bots`, `get_bot` (name + limit), `search` (query + context).

## Supported agents

The exported data + MCP server can be consumed by any agent that supports MCP (or reads files directly):

**Local agents (stdio MCP works directly):**

- **Codex** (OpenAI) — add the server to `~/.codex/config.toml` or via `codex mcp add`.
- **Claude Code** (Anthropic) — `claude mcp add grok-bot -- python3 /path/to/grok-bot-mcp.py /path/to/export`.
- **OpenCode** — MCP (`grok-bot`) and/or the bundled **skill** (`grok-export`).
- **Cursor** — add it under Cursor Settings → MCP.
- **Windsurf**, **Cline**, **Roo Code**, **Kilo Code**, **Zed**, **GitHub Copilot** — any MCP-capable agent, same stdio config.

**Cloud agents (need a remote MCP endpoint):**

- **Grok Bot** — runs on xAI's cloud VM and cannot reach your local stdio process directly. It *does* support MCP, but only via a publicly reachable MCP server (HTTP). To let Grok Bot query the data, host `grok-bot-mcp.py` behind an HTTP MCP gateway (or deploy the exported files somewhere Grok Bot can read them).

**No MCP?** Just point the agent at the exported folder — read `AGENTS.md` first, then the per-bot `messages.jsonl` / `conversation.md`.

## How it works

1. Decrypts `sso` / `sso-rw` cookies from the local Chrome cookie DB (macOS Keychain, Windows DPAPI, or `--cookie`).
2. Connects to `wss://grok.com/ws/bot/` (JSON-RPC over WebSocket).
3. `bot.roster` lists all bots; `bot.transcript.offbox` pages through each bot's history.
4. Attachments download via `bot.command` + `readAttachmentChunk` in 4 MB chunks.
5. Normalizes everything into the Agent-friendly structure above.

## Disclaimer

This is an **unofficial** tool, not affiliated with or endorsed by xAI. It relies on reverse-engineered internal endpoints that may change without notice. Use it only to back up your own account data, and respect grok.com's Terms of Service.

## License

[MIT](LICENSE)
