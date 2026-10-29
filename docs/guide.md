# Using grok-export-tool

[English](guide.md) · [中文](guide.zh-CN.md) · [README](../README.md)

A step-by-step backup of your own [grok.com](https://grok.com) account on a Mac. The tool has two products in one command: **Grok Bots** (roster, transcripts, attachments) and **regular Grok chats**. You choose bots, chats, or both.

This is an unofficial tool. It is a local backup, not an xAI product. The exporter’s progress lines are in Chinese even on an English Mac.

## 1. Before you start

You need all of the following:

1. A Mac.
2. Google Chrome, logged in at [grok.com](https://grok.com) as the account you want to back up. Safari, Firefox, Arc, and Chromium are not read.
3. That login lives in the Chrome profile **Default**, **Profile 1**, or **Profile 2**. Other profiles are ignored.
4. Python 3.9 or newer (`python3 --version`).
5. The account is yours.

Grok Bots and regular chats are separate. A Bot is an agent with an id, a roster entry, and a transcript. A regular chat is a grok.com conversation. `--mode bot` (the default) exports Bots. `--mode chat` exports regular chats. `--mode all` exports both, into two directories.

Have Chrome signed in before you run anything. The tool reuses that session. It does not open a login window and it does not ask for a password you type yourself. macOS will ask once for Keychain access; that step is below.

## 2. Install

```bash
git clone https://github.com/LofiSu/grok-export-tool.git
cd grok-export-tool
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

`requirements.txt` installs `websocket-client` and `cryptography`. Both modes need them, because both modes decrypt Chrome’s cookie database first. Chat requests themselves use the Python standard library.

Keep the virtualenv active in the terminal where you run the exporter. The MCP server has no third-party imports, so its command can be system `python3`.

Confirm the command line:

```bash
python3 grok-bot-export.py --help
```

You should see `--mode {bot,chat,all}`, `--skip-attachments` / `--messages-only`, and `--workers`.

## 3. Export

Run these from the repository root, with the virtualenv active. The first successful cookie read triggers a macOS dialog for the Keychain item **Chrome Safe Storage**. Choose **Allow**. Details are in [Troubleshooting](#7-troubleshooting).

### Grok Bots, full archive

Messages, events, voice-call records, and attachment files:

```bash
python3 grok-bot-export.py
```

or:

```bash
./export.sh
```

Default directory: `~/Downloads/grok-bot-export-YYYYMMDD/`.

### Grok Bots, messages only

The transcript is still complete. Attachment bytes are not downloaded. `messages.jsonl` still records `localFile` when the transcript names a file, so a later full run knows where to put it.

```bash
python3 grok-bot-export.py --messages-only
```

`--skip-attachments` is the same flag. `./export-messages.sh` wraps it.

### Regular Grok chats

```bash
python3 grok-bot-export.py --mode chat
```

or:

```bash
./export-chat.sh
```

Default directory: `~/Downloads/grok-chat-export-YYYYMMDD/`.

This writes conversation text and raw response JSON. It does not download attachment files. `--messages-only` has no effect here.

### Both

```bash
python3 grok-bot-export.py --mode all
```

With no directory argument, Bots go to `~/Downloads/grok-bot-export-YYYYMMDD/` and chats go to `~/Downloads/grok-chat-export-YYYYMMDD/`.

There is no `export-all.sh`. `--messages-only` together with `--mode all` skips Bot attachments and still writes chats.

### Choose a directory

```bash
python3 grok-bot-export.py ~/Backups/grok-bots
python3 grok-bot-export.py --messages-only ~/Backups/grok-bots
python3 grok-bot-export.py --mode chat ~/Backups/grok-chats
python3 grok-bot-export.py --mode all ~/Backups/grok-bots
```

The last command writes Bots to `~/Backups/grok-bots` and chats to `~/Backups/grok-bots-chat`. The `-chat` suffix is added only when `--mode all` and a directory are both set. A chat-only run uses the directory you passed, with no suffix.

### Attachment workers

Bot downloads use 6 threads unless you change it. Each chunk is 4 MB, which is the request size the exporter sends.

```bash
python3 grok-bot-export.py --workers 4
```

A file that already exists and is non-empty is left in place. An empty file is downloaded again. Re-running a full Bot export is the way to retry failures.

### What one run includes

Each mode walks the whole list the session returns. There is no flag for a single Bot or a single chat. Afterward, open one folder, or ask the MCP server for one Bot by name.

## 4. Where the files go

Defaults sit under `~/Downloads/`, outside the git repository. That is deliberate: an export can contain full transcripts and files, and it should not be committed.

A cookie failure exits before any directory is created. If the Bot WebSocket fails after cookies succeed, `export_bots` may already have created an empty output directory.

## 5. Reading the archive

### Grok Bots

```
grok-bot-export-YYYYMMDD/
  AGENTS.md                 short map for an agent; read this first if you are handing the folder to one
  _index.md                 one link per Bot
  roster.json               the roster as returned, under "agents"
  01_<name>/
    meta.json               that Bot’s roster record (name, agentId, status, lastTurnAt, and the rest of the record)
    messages.jsonl          one normalized JSON object per line
    conversation.md         the same transcript, with roles, for reading
    transcript.json         decoded entries, kept so nothing depends on the normalized view
    attachments/            downloaded files
```

Folder numbers are at least two digits (`01`, `02`, …). The name is sanitized: path characters are replaced, and it is trimmed to 60 characters.

Open `_index.md`, then a `conversation.md`. For scripts or an agent, prefer `messages.jsonl`.

| Field | Meaning |
| --- | --- |
| `seq` | Order from the transcript |
| `type` | `message`, `send-message`, `user-attachment`, `event`, `voice-call`, or another entry kind |
| `role` | `user` or `assistant` on message entries. `send-message` is stored as `assistant`. `user-attachment` is stored as `user` |
| `content` | Text. Empty for a bare user attachment |
| `timestamp`, `timestampMs` | Local time string, and the original millisecond value |
| `attachment` | File name and path fields when this entry has a file |
| `localFile` | Path relative to the Bot folder, such as `attachments/0007_name` |
| `event`, `call` | Payload for those entry kinds |
| `entryId`, `fromAgent`, `replyTo`, `messageType`, `raw` | Present when the transcript has them |

`meta.json` is the roster object, not a reduced schema. `name`, `agentId`, `status`, and `lastTurnAt` are the fields the MCP server displays.

### Regular chats

```
grok-chat-export-YYYYMMDD/
  _index.md
  conversations.jsonl       every message of every chat, one object per line
  conversations/
    0001_<title>.md         readable transcript
    0001_<title>.json       id, title, times, and the raw response list
```

Numbers are at least four digits. Titles are sanitized the same way as Bot names.

| Field in `conversations.jsonl` | Meaning |
| --- | --- |
| `conversationId` | grok.com conversation id |
| `title` | Conversation title, or `未命名对话` when the API omits one |
| `role` | `user` when the sender is `human`, otherwise `assistant` |
| `sender` | Sender string from the API |
| `content` | Message text. When the body is not a string, the JSON text of that body |
| `timestamp`, `timestampMs` | Local time string, and `createTime` |

The per-conversation `.json` file keeps the raw `messages` array plus `createTime` and `modifyTime`. There is no `AGENTS.md` in a chat export, and the MCP server does not index it.

## 6. MCP server for OpenCode

The server is `grok-bot-mcp.py`. It reads a Grok Bot directory and answers three tools. Point it at the Bot folder from section 5, the one that contains `roster.json` and `01_…` directories.

From a terminal, the process is:

```bash
python3 /absolute/path/to/grok-export-tool/grok-bot-mcp.py \
  /absolute/path/to/grok-bot-export-YYYYMMDD
```

It speaks JSON-RPC on stdin/stdout and waits. You do not run that line for daily use; the agent client starts it. The script expands `~` in the directory argument. Prefer an absolute path anyway, because some clients do not run the command through a shell.

If you leave the directory out, the server selects the newest `~/Downloads/grok-bot-export-*` by modification time. It does not look at `grok-chat-export-*`. Pass the Bot path explicitly so a chat folder or an old download is not what gets opened.

### OpenCode

Current OpenCode config (the published schema at `https://opencode.ai/config.json`) uses `mcp.servers`. Edit the global file `~/.config/opencode/opencode.json`, or create `opencode.json` in a project.

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "grok-bot": {
        "type": "local",
        "command": [
          "python3",
          "/absolute/path/to/grok-export-tool/grok-bot-mcp.py",
          "/absolute/path/to/grok-bot-export-YYYYMMDD"
        ],
        "enabled": true
      }
    }
  }
}
```

Replace both paths. If the exporter’s virtualenv is the Python you trust and you would rather use it, put that interpreter first:

```text
/absolute/path/to/grok-export-tool/.venv/bin/python
```

The MCP file does not import `websocket` or `cryptography`, so system `python3` is enough.

Start a new OpenCode session so it reloads config. Ask it to use the `grok-bot` tools. A concrete prompt is enough: list the bots, then open one by the name you see.

| Tool | Arguments | Behavior |
| --- | --- | --- |
| `list_bots` | none | One line per Bot: name, `agentId`, message count, last active time. The wording is Chinese |
| `get_bot` | `bot` (required), `limit` (default 200) | Matches a folder prefix (`01`), then a substring of the name or `agentId`. Returns metadata and messages up to `limit` |
| `search` | `query` (required), `context` (default 2) | Case-sensitive substring of `content`. Up to 10 hits, with neighboring messages |

### If OpenCode rejects `servers`

Some older builds want the server directly under `mcp`. The current schema marks that shape deprecated. Use it only when the `servers` form is rejected:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "grok-bot": {
      "type": "local",
      "command": [
        "python3",
        "/absolute/path/to/grok-export-tool/grok-bot-mcp.py",
        "/absolute/path/to/grok-bot-export-YYYYMMDD"
      ]
    }
  }
}
```

### OpenCode skill

Clone this repository and open it as the project. OpenCode loads `.opencode/skills/grok-export/SKILL.md`. The skill name is **Grok Export**. Ask, in ordinary language, to export or to look something up in the Bot archive. The skill tells the agent which command to run and to prefer MCP over pasting whole files into the prompt.

### Other agents

Any stdio MCP client can launch the same program. Three common shapes:

Claude Code, user or project scope. Project scope is `.mcp.json` at the project root (approve it when Claude Code asks). User scope lives in `~/.claude.json`. The same JSON is the `mcpServers` object either way:

```json
{
  "mcpServers": {
    "grok-bot": {
      "type": "stdio",
      "command": "python3",
      "args": [
        "/absolute/path/to/grok-export-tool/grok-bot-mcp.py",
        "/absolute/path/to/grok-bot-export-YYYYMMDD"
      ]
    }
  }
}
```

Codex reads `~/.codex/config.toml` (and `.codex/config.toml` in a trusted project):

```toml
[mcp_servers.grok-bot]
command = "python3"
args = [
  "/absolute/path/to/grok-export-tool/grok-bot-mcp.py",
  "/absolute/path/to/grok-bot-export-YYYYMMDD",
]
```

Cursor uses `.cursor/mcp.json` in the project or `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "grok-bot": {
      "command": "python3",
      "args": [
        "/absolute/path/to/grok-export-tool/grok-bot-mcp.py",
        "/absolute/path/to/grok-bot-export-YYYYMMDD"
      ]
    }
  }
}
```

Those clients change their file layouts. If a key is rejected, the vendor’s MCP page is the authority; the process to launch does not change.

Do not point the server at a chat export and expect bots. `list_bots` looks for subfolders that contain `meta.json`. A chat directory has none, and the reply is the Chinese sentence that no export was found.

## 7. Troubleshooting

### Keychain prompt

The exporter runs:

```text
security find-generic-password -w -s "Chrome Safe Storage" -a Chrome
```

macOS shows a dialog asking to allow access to that item. Choose Allow, or Always Allow so later runs stay quiet. The password stays on the machine and is used to decrypt Chrome’s cookie database. Do not paste it into an issue, a chat, or a commit. [SECURITY.md](../SECURITY.md) lists what a report must leave out.

If you choose Deny, cookie decryption fails. The script exits with:

```text
未能从 Chrome 解密出 grok.com 登录态
```

Open **Keychain Access**, find **Chrome Safe Storage**, and allow the terminal app you are using (Terminal, iTerm, the IDE’s integrated terminal). Then run the export again. A headless or SSH session may be unable to answer the dialog; run it once in a graphical session.

### Chrome is not logged in

The same exit line covers three different causes:

- grok.com is not logged in inside Google Chrome.
- The login is in a profile other than Default, Profile 1, or Profile 2. Sign in inside one of those three. This tool does not scan any further profile.
- Keychain access was denied, so the cookies could not be decrypted.

The tool needs both cookie names `sso` and `sso-rw`. A page that looks logged in but is missing either cookie fails the same way. Quit Chrome only if you need to; being logged in matters more than Chrome being closed. Log in, confirm the profile, allow Keychain, and run again.

### Empty Bot roster

The log line `找到 0 个 bot` means the WebSocket roster returned no agents. The directory is still written: `AGENTS.md`, `_index.md`, and `roster.json`.

Regular chats are not Bots. They show up only under `--mode chat` or `--mode all`, in the chat directory. An account that only uses the main grok.com chat will have an empty Bot roster.

Also check that Chrome is the right account. A second Google account in another profile is invisible unless it is Default, Profile 1, or Profile 2.

### Empty chat list

`找到 0 个普通会话` means the chat list was empty or the list request failed before any page arrived. Look just above it. `会话列表请求失败（HTTP …)` means grok.com refused the list. HTTP 429 and HTTP 5xx are retried up to five times with a short backoff. A final failure stops the list. Fix the login or wait, then run `--mode chat` again.

A warning on a single title (`拉取失败`) means that conversation was saved with whatever messages had already arrived, which can be zero. Other conversations in the same run are unaffected.

### Cookie database error

If Python prints a traceback while copying Chrome’s `Cookies` file, quit Chrome completely (including background processes) and run the export again. The tool copies the database to a temp file, reads it, and deletes the copy. It does not print cookie values.

### Attachments missing

`--messages-only` skips downloads on purpose. On a full run, the summary line reports how many attachment jobs succeeded. Re-run the full Bot export to retry files that are missing or empty. Files that are already non-empty stay as they are.

Chat mode never writes an `attachments/` folder.

### MCP says there are no bots

Pass the Bot directory, not the repository root and not the chat directory. The folder you pass should contain subfolders with `meta.json`. Restart the agent client after changing the path. Tool replies are Chinese; an empty result includes the sentence that tells you to run the exporter and check the directory.

### The run dies on the WebSocket or mid-list

grok.com can change these interfaces without notice. Pull the latest `main` and try again. If it still fails, open an issue with the error text and the commit you ran. Leave out cookies, the Keychain password, agent ids, and transcript text. Security reports go through [SECURITY.md](../SECURITY.md), not a public issue.

## 8. Safety

- Back up an account you own.
- Keep `~/Downloads/grok-bot-export-*` and `~/Downloads/grok-chat-export-*` private. They can hold full transcripts and files.
- Do not commit exports, Chrome’s cookie database, or Keychain material. The default output path is outside the repository.
- `grok-bot-mcp.py` does not open a network connection. Give it only an export you trust. The exporter does open connections to grok.com, using your existing session, to read history.
- The tool does not send a new chat message and does not delete bots or conversations.
- Cookie decryption exists so an existing Chrome login can be reused. That material stays on the machine.
- The project is not affiliated with xAI. Follow grok.com’s terms. Interfaces can break.

## 9. Where to go next

- [README](../README.md) · [中文说明](../README.zh-CN.md)
- [Project site](https://lofisu.github.io/grok-export-tool/) once GitHub Pages is publishing from `main`
- [Contact and donate](../README.md#contact--connect) — GitHub [@LofiSu](https://github.com/LofiSu), [lofisuchat@gmail.com](mailto:lofisuchat@gmail.com), [Rowan on X](https://x.com/QiuMilorw)
