[English](README.md) · [中文](README.zh-CN.md)

> **Poster forthcoming.** An approved image will be embedded here (`docs/assets/poster.png`). This release does not ship a generated stand-in.

# grok-export-tool

A local copy of your [grok.com](https://grok.com) history: every **Grok Bot**, with attachments, and your **regular Grok chats**. The Bot archive is laid out for people and for agents, and a small **MCP server** lets [OpenCode](https://opencode.ai) and other assistants read it back.

Unofficial. It runs on your Mac, in the Chrome profile where you are already logged in. It is a backup of your own account.

## Features

- Exports every Grok Bot the signed-in Chrome session can see: roster, full transcript, and attachments (images, video, and other files), in parallel 4 MB chunks.
- Exports regular Grok chats to a second folder: a Markdown file per conversation, raw JSON, and one combined JSONL file.
- Can skip Bot attachment downloads when you only want the text (`--messages-only`).
- Writes an archive an agent can walk: normalized JSONL, readable Markdown, raw JSON, and an index.
- Includes a stdio MCP server with no third-party dependencies (`list_bots`, `get_bot`, `search`) for the **Bot** archive.
- Ships an OpenCode skill at `.opencode/skills/grok-export/` for the export-and-query workflow.

The exporter reads history you already have. It does not send new chats and it does not delete anything. Bot history goes over grok.com’s bot WebSocket. Regular chats go over grok.com’s app-chat HTTP API, which can respond with HTTP 429; those requests are retried.

macOS and Google Chrome only. Chrome profiles scanned: Default, Profile 1, and Profile 2. The MCP server reads a Grok Bot export. Regular chat exports stay files you open yourself.

## Quick start

```bash
git clone https://github.com/LofiSu/grok-export-tool.git
cd grok-export-tool
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Python 3.9 or newer. Dependencies are `websocket-client` and `cryptography` ([requirements.txt](requirements.txt)). The MCP server uses the standard library only, so it can run on system `python3` even when the exporter is in a virtualenv.

```bash
python3 grok-bot-export.py                  # Grok Bots, messages and attachments
python3 grok-bot-export.py --messages-only  # Grok Bots, text only
python3 grok-bot-export.py --mode chat      # regular Grok chats
python3 grok-bot-export.py --mode all       # both
```

The same three Bot/chat entry points exist as `./export.sh`, `./export-messages.sh`, and `./export-chat.sh`.

The first run asks macOS for the Keychain item **Chrome Safe Storage**. Allow it. Progress lines are printed in Chinese. Output lands in `~/Downloads/` unless you pass a directory.

The [usage guide](docs/guide.md) walks through install, each export mode, the archive, OpenCode, and the failures that actually happen (Keychain, a logged-out Chrome, an empty roster).

## Tutorial

- English: [docs/guide.md](docs/guide.md)
- 中文：[docs/guide.zh-CN.md](docs/guide.zh-CN.md)
- Site (after GitHub Pages is enabled on `main`): [lofisu.github.io/grok-export-tool](https://lofisu.github.io/grok-export-tool/)

## MCP

`grok-bot-mcp.py` speaks MCP over stdio. Give it the **Bot** export directory. If you omit the path, it picks the newest `~/Downloads/grok-bot-export-*` folder. It does not open a network connection.

OpenCode’s current config schema puts servers under `mcp.servers`. In `~/.config/opencode/opencode.json` (or a project `opencode.json`):

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "grok-bot": {
        "type": "local",
        "command": [
          "python3",
          "/absolute/path/grok-bot-mcp.py",
          "/absolute/path/grok-bot-export-YYYYMMDD"
        ]
      }
    }
  }
}
```

Tools:

| Tool | Role |
| --- | --- |
| `list_bots` | Names, ids, message counts, last active time |
| `get_bot` | One bot, by name, id fragment, or folder prefix such as `01`. `limit` defaults to 200 |
| `search` | Case-sensitive substring on message text, with neighboring lines. `context` defaults to 2 |

Older OpenCode builds put the server object directly under `mcp` (that shape is deprecated in the current schema). Claude Code, Codex, and Cursor launch the same process with their own config files. Paths, tool arguments, and those clients are in the [guide](docs/guide.md#6-mcp-server-for-opencode).

OpenCode discovers `.opencode/skills/grok-export/` when this repository is the project. The skill’s name is **Grok Export**.

## Output layout

Grok Bots (default, or the Bot half of `--mode all`):

```
~/Downloads/grok-bot-export-YYYYMMDD/
  AGENTS.md
  _index.md
  roster.json
  01_<bot name>/
    meta.json
    transcript.json
    messages.jsonl
    conversation.md
    attachments/
```

`messages.jsonl` is one JSON object per line. Fields you can rely on: `seq`, `type` (`message`, `send-message`, `user-attachment`, `event`, `voice-call`), `role` (`user` or `assistant` when the entry has one), `content`, `timestamp`, `timestampMs`, `attachment`, `localFile`, `event`, `call`.

Regular chats (`--mode chat`, or the chat half of `--mode all`):

```
~/Downloads/grok-chat-export-YYYYMMDD/
  _index.md
  conversations.jsonl
  conversations/
    0001_<title>.md
    0001_<title>.json
```

`conversations.jsonl` fields: `conversationId`, `title`, `role`, `sender`, `content`, `timestamp`, `timestampMs`. Chat export records response text and the raw response JSON. It does not download attachment files.

Pass a directory to override the default. With `--mode all` and a directory, Bots go to that directory and chats go to the same path with `-chat` appended. Attachment downloads skip a file that is already present and non-empty. `--workers` defaults to 6 and applies to Bot attachments. `--messages-only` is an alias of `--skip-attachments` and only affects Bots.

Start with `_index.md`. For a Bot, read `conversation.md` or `messages.jsonl`. `AGENTS.md` in a Bot export is a short map of that folder for an agent.

## Disclaimer

This is an unofficial tool. It is not affiliated with or endorsed by xAI. It depends on grok.com interfaces that can change without notice. Use it to back up an account you own, and follow grok.com’s terms. Treat the export folder as private. Vulnerability reports stay private and must not include cookies or transcripts; see [SECURITY.md](SECURITY.md).

## Contact & Connect

Questions, corrections, and collaboration are welcome — usage notes, doc fixes, and help with platforms beyond this Mac + Chrome path.

- GitHub: [github.com/LofiSu](https://github.com/LofiSu)
- Email: [lofisuchat@gmail.com](mailto:lofisuchat@gmail.com)
- X: [x.com/QiuMilorw](https://x.com/QiuMilorw) (Rowan)

## Donate

If the backup saved you a tedious afternoon, [GitHub Sponsors](https://github.com/sponsors/LofiSu) is there. If Sponsors is not enabled on the account yet, a note to [lofisuchat@gmail.com](mailto:lofisuchat@gmail.com) is enough — donations by email are welcome. Only if you want to.

## License

[MIT](LICENSE)
