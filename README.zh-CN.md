[English](README.md) · [中文](README.zh-CN.md)

![grok-export-tool。导出 Grok Bot 和普通对话。MCP server 与 Agent skills。全程本地，无需 API key。](docs/assets/poster.png)

# grok-export-tool

导出你的 **Grok Bot** 和**普通对话**。本地命令行、stdio MCP server，以及 Agent skills。全程本地，无需 API key。

它备份这台电脑上已经登录的 [grok.com](https://grok.com) 账号。每个 Bot 都会保存名单、完整记录和附件。普通对话写到另一个目录。人和 Agent 都能读这份归档：一个很小的 MCP server 和一份 Agent Skill，让 [OpenCode](https://opencode.ai)、Claude Code、Codex 等查询 Bot 归档。

它读取你已经有的历史。它不发送新对话。

[特性](#特性) · [快速开始](#快速开始) · [教程](#教程) · [MCP](#mcp) · [Agent skills](#agent-skills) · [输出布局](#输出布局) · [联系](#联系) · [捐赠](#捐赠)

## 特性

- **命令行。** `grok-bot-export.py` 可以导出 Bot、普通对话，或两者一起（`--mode bot`、`--mode chat`、`--mode all`）。`--messages-only` 会跳过 Bot 的附件下载。
- **Grok Bot。** 名单、完整记录、附件（图片、视频和其他文件）。附件按 4MB 分块并行下载。
- **普通对话。** 另一个目录：每个会话一份 Markdown、一份原始 JSON，外加一个合并的 JSONL。
- **归档。** 归一化 JSONL、可读 Markdown、原始 JSON，以及索引。
- **MCP。** 零第三方依赖的 stdio server：`list_bots`、`get_bot`、`search`。它读取 Bot 归档。
- **Skills。** `.claude/skills/grok-export/` 是一份 Agent Skill，Claude Code、OpenCode，以及其他会加载这个目录的 Agent 都能用。

Bot 历史走 grok.com 的 Bot WebSocket。普通对话走 grok.com 的 app-chat HTTP 接口；这个接口可能返回 HTTP 429，脚本会重试。MCP server 不索引普通对话导出。那些文件请自己打开，或把目录交给 Agent。

## 快速开始

```bash
git clone https://github.com/LofiSu/grok-export-tool.git
cd grok-export-tool
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

需要 Python 3.9 或更高版本。依赖是 `websocket-client` 和 `cryptography`（[requirements.txt](requirements.txt)）。Windows 上若要自动解密 cookie，还需要 `pywin32`。MCP server 只用标准库。

```bash
python3 grok-bot-export.py                  # Grok Bot：消息和附件
python3 grok-bot-export.py --messages-only  # Grok Bot：只要文字
python3 grok-bot-export.py --mode chat      # 普通 Grok 对话
python3 grok-bot-export.py --mode all       # 两者都导出
```

三个入口也可以写成 `./export.sh`、`./export-messages.sh`、`./export-chat.sh`。

| 平台 | Cookie 登录 |
| --- | --- |
| macOS | 钥匙串项目 **Chrome Safe Storage**。会查看 Default、Profile 1、Profile 2。 |
| Windows | 安装 `pywin32` 后走 DPAPI。若是 App-Bound Encryption，请用 `--cookie`。 |
| Linux | 尽力而为。失败时用 `--cookie`。 |

```bash
python3 grok-bot-export.py --cookie "sso=...; sso-rw=..."
```

从你自己浏览器的 DevTools 里复制 `sso` 和 `sso-rw`。不要把这些值贴进 issue、聊天或 git。

进度日志是中文。未指定目录时，文件写到 `~/Downloads/`。

逐步说明在[教程](#教程)。

## 教程

同一份教程，中英都有，网站和仓库里各一份。内容包括安装、每种导出、归档、MCP、skills，以及真正会遇到的问题。

- **网站：** [lofisu.github.io/grok-export-tool](https://lofisu.github.io/grok-export-tool/) · [中文首页](https://lofisu.github.io/grok-export-tool/index.zh-CN.html)
- **中文：** [docs/guide.zh-CN.md](docs/guide.zh-CN.md) · [网站上的教程](https://lofisu.github.io/grok-export-tool/guide.zh-CN.html)
- **English:** [docs/guide.md](docs/guide.md) · [on the site](https://lofisu.github.io/grok-export-tool/guide.html)

## MCP

`grok-bot-mcp.py` 通过 stdio 提供 MCP。把 **Bot** 导出目录传给它。省略路径时，它会选用 `~/Downloads/grok-bot-export-*` 里最新的一个。它自己不发起网络连接。

OpenCode 当前的配置 schema 把服务器写在 `mcp.servers` 下。编辑 `~/.config/opencode/opencode.json`（或项目里的 `opencode.json`）：

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

| 工具 | 作用 |
| --- | --- |
| `list_bots` | 名称、id、消息数、最后活跃时间 |
| `get_bot` | 按名称、id 片段，或 `01` 这样的文件夹前缀取一个 bot。`limit` 默认 200 |
| `search` | 在消息正文里做区分大小写的子串搜索，并带上相邻消息。`context` 默认 2 |

Claude Code、Codex、Cursor 启动的是同一个进程，只是配置文件不同。路径和示例见[教程](docs/guide.zh-CN.md#6-opencode-的-mcp-server)。

## Agent skills

Skill 在 `.claude/skills/grok-export/SKILL.md`。

- **Claude Code** 会读取项目里的 `.claude/skills/`。
- **OpenCode** 也会读这个目录，或在配置里写 `"skills": [".claude/skills"]`。
- **Codex、Copilot、Gemini CLI、Cursor** — 按各自文档，把 `grok-export/` 拷到它们的 skills 目录。

Skill 名称是 **grok-export**。用平常的话说要导出，或要在 Bot 归档里查一件事。

## 输出布局

Grok Bot（默认，或 `--mode all` 的 Bot 那一半）：

```
~/Downloads/grok-bot-export-YYYYMMDD/
  AGENTS.md
  _index.md
  roster.json
  01_<bot 名称>/
    meta.json
    transcript.json
    messages.jsonl
    conversation.md
    attachments/
```

`messages.jsonl` 每行一个 JSON。可以依赖的字段：`seq`、`type`（`message`、`send-message`、`user-attachment`、`event`、`voice-call`）、`role`（有角色时为 `user` 或 `assistant`）、`content`、`timestamp`、`timestampMs`、`attachment`、`localFile`、`event`、`call`。

普通对话（`--mode chat`，或 `--mode all` 的对话那一半）：

```
~/Downloads/grok-chat-export-YYYYMMDD/
  _index.md
  conversations.jsonl
  conversations/
    0001_<标题>.md
    0001_<标题>.json
```

`conversations.jsonl` 的字段：`conversationId`、`title`、`role`、`sender`、`content`、`timestamp`、`timestampMs`。普通对话导出保存回复文本和原始 JSON，不下载附件文件。

把目录作为第一个参数可以改掉默认位置。`--mode all` 同时又给了目录时，Bot 写到该目录，普通对话写到同一路径后面加上 `-chat`。进程会把 umask 设为 077，然后把目录标成 `0700`、文件标成 `0600`。附件若已存在且不是空文件，会跳过。`--workers` 默认 6（允许 1–32），只作用于 Bot 附件。`--messages-only` 与 `--skip-attachments` 是同一个开关，只影响 Bot。

先看 `_index.md`。读某个 Bot 时打开 `conversation.md` 或 `messages.jsonl`。Bot 导出里的 `AGENTS.md` 是给 Agent 的简短目录说明。

## 免责声明

这个项目由社区在公开仓库里维护，不是 xAI 发布的产品。它依赖 grok.com 的接口，这些接口可能随时改变。请只备份你自己拥有的账号，并遵守 grok.com 的条款。导出目录视为私密。漏洞请私下报告，报告中不要包含 cookie 或对话内容，见 [SECURITY.md](SECURITY.md)。

## 联系

欢迎来信，也欢迎一起做。使用上的问题、文档勘误、某个平台上的帮助，或只是打个招呼，都可以。

- GitHub：[github.com/LofiSu](https://github.com/LofiSu)
- 邮箱：[lofisuchat@gmail.com](mailto:lofisuchat@gmail.com)

## 捐赠

如果这次备份省下了时间，一份赞助就是很好的致谢。随缘就好。

- [GitHub Sponsors](https://github.com/sponsors/LofiSu)
- 也可以写信到 [lofisuchat@gmail.com](mailto:lofisuchat@gmail.com)

## 许可证

[MIT](LICENSE)
