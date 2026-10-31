[English](README.md) · [中文](README.zh-CN.md)

![grok-export-tool. Export Grok Bots and chats. MCP server and agent skills. Fully local, no API key.](docs/assets/poster.png)

# grok-export-tool

Export **Grok Bots** and **regular chats** from the [grok.com](https://grok.com) account already signed in on this machine. A local CLI, a stdio MCP server, and an Agent Skill. Fully local, no API key. It reads history you already have, and does not send new chats.

Each Bot is saved with its roster, full transcript, and attachments. Regular chats go to a second folder. The MCP server and skill let [OpenCode](https://opencode.ai), Claude Code, Codex, and others query the Bot archive.

[Features](#features) · [Quick start](#quick-start) · [Tutorial](#tutorial) · [MCP](#mcp) · [Agent skills](#agent-skills) · [Output layout](#output-layout) · [Contact](#contact) · [Donate](#donate)

## Features

- **CLI.** `grok-bot-export.py` exports Bots, regular chats, or both (`--mode bot`, `--mode chat`, `--mode all`). `--messages-only` skips Bot attachment downloads.
- **Grok Bots.** Roster, full transcript, and attachments (images, video, and other files), in parallel 4 MB chunks.
- **Regular chats.** One Markdown file and one raw JSON file per conversation, plus one combined JSONL file.
- **Archive.** JSONL, readable Markdown, raw JSON, and an index.
- **MCP.** A stdio server with no third-party dependencies: `list_bots`, `get_bot`, `search`. It reads the Bot archive only.
- **Skill.** `.claude/skills/grok-export/` is an Agent Skill for Claude Code, OpenCode, and other agents that load that folder.

Bot history goes over grok.com’s bot WebSocket. Regular chats go over grok.com’s app-chat HTTP API. HTTP 429 responses are retried. The MCP server does not index a chat export. Open those files, or point an agent at the folder.

## Quick start

```bash
git clone https://github.com/LofiSu/grok-export-tool.git
cd grok-export-tool
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Python 3.9 or newer. Dependencies: `websocket-client` and `cryptography` ([requirements.txt](requirements.txt)). On Windows, automatic cookie decryption also needs `pywin32`. The MCP server uses the standard library only.

```bash
python3 grok-bot-export.py                  # Grok Bots, messages and attachments
python3 grok-bot-export.py --messages-only  # Grok Bots, text only
python3 grok-bot-export.py --mode chat      # regular Grok chats
python3 grok-bot-export.py --mode all       # both
```

Shell wrappers: `./export.sh`, `./export-messages.sh`, and `./export-chat.sh`.

| Platform | Cookie login |
| --- | --- |
| macOS | Keychain item **Chrome Safe Storage**. Profiles scanned: Default, Profile 1, Profile 2. |
| Windows | DPAPI when `pywin32` is installed. App-Bound Encryption needs `--cookie`. |
| Linux | Legacy fixed key or plaintext only. If that fails, use `--cookie`. |

```bash
python3 grok-bot-export.py --cookie "sso=...; sso-rw=..."
```

Copy `sso` and `sso-rw` from your own browser’s DevTools. Do not paste those values into an issue, a chat, or git.

Progress lines are in Chinese. Output goes to `~/Downloads/` unless you pass a directory. Steps are in the [tutorial](#tutorial).

## Tutorial

The same guide, in both languages, on the site and in the repo: install, each export mode, the archive, MCP, skills, and troubleshooting.

- **Site:** [lofisu.github.io/grok-export-tool](https://lofisu.github.io/grok-export-tool/) · [中文首页](https://lofisu.github.io/grok-export-tool/index.zh-CN.html)
- **English:** [docs/guide.md](docs/guide.md) · [on the site](https://lofisu.github.io/grok-export-tool/guide.html)
- **中文:** [docs/guide.zh-CN.md](docs/guide.zh-CN.md) · [网站上的教程](https://lofisu.github.io/grok-export-tool/guide.zh-CN.html)

## MCP

`grok-bot-mcp.py` speaks MCP over stdio and does not open a network connection. Pass the **Bot** export directory. If you omit the path, it uses the newest `~/Downloads/grok-bot-export-*` directory by modification time.

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

| Tool | Role |
| --- | --- |
| `list_bots` | Names, ids, message counts, last active time |
| `get_bot` | One bot, by name, id fragment, or folder prefix such as `01`. `limit` defaults to 200 |
| `search` | Case-sensitive substring on message text, with neighboring lines. `context` defaults to 2 |

Claude Code, Codex, and Cursor launch the same process from their own config files. Paths and examples are in the [guide](docs/guide.md#6-mcp-server-for-opencode).

## Agent skills

The skill is `.claude/skills/grok-export/SKILL.md`. The name is **grok-export**.

- **Claude Code** reads `.claude/skills/` in the project.
- **OpenCode** reads that folder too, or you can set `"skills": [".claude/skills"]`.
- **Codex, Copilot, Gemini CLI, Cursor** — copy `grok-export/` into the skills directory that agent documents.

Ask the agent to export, or to look something up in the Bot archive.

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

`messages.jsonl` is one JSON object per line. Fields: `seq`, `type` (`message`, `send-message`, `user-attachment`, `event`, `voice-call`), `role` (`user` or `assistant` when the entry has one), `content`, `timestamp`, `timestampMs`, `attachment`, `localFile`, `event`, `call`.

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

The first argument sets the output directory. With `--mode all` and a directory, Bots go to that directory and chats go to the same path with `-chat` appended. The process sets umask 077, then marks directories `0700` and files `0600`. Attachment downloads skip a file that is already present and non-empty. `--workers` defaults to 6 (allowed range 1–32) and applies to Bot attachments. `--messages-only` is an alias of `--skip-attachments` and only affects Bots.

Start with `_index.md`. For a Bot, read `conversation.md` or `messages.jsonl`. `AGENTS.md` in a Bot export is a short map of that folder for an agent.

## Disclaimer

Maintained in this public repository by the community. Not published by xAI. grok.com’s interfaces can change without notice. Back up an account you own, and follow grok.com’s terms. Treat the export folder as private. Report vulnerabilities in private, and do not include cookies or transcripts. See [SECURITY.md](SECURITY.md).

## Contact

Usage questions, doc fixes, and platform help:

- GitHub: [github.com/LofiSu](https://github.com/LofiSu)
- X: [X / @su_lofi](https://x.com/su_lofi)
- Email: [lofisuchat@gmail.com](mailto:lofisuchat@gmail.com)

## Donate

Sponsor via GitHub Sponsors, or send email.

- [GitHub Sponsors](https://github.com/sponsors/LofiSu)
- Email: [lofisuchat@gmail.com](mailto:lofisuchat@gmail.com)

## License

[MIT](LICENSE)
