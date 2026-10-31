[English](README.md) · [中文](README.zh-CN.md)

![grok-export-tool。导出 Grok Bot 和普通对话。MCP server 与 Agent skills。全程本地，无需 API key。](docs/assets/poster.png)

# grok-export-tool

导出本机已登录的 [grok.com](https://grok.com) 账号里的 **Grok Bot** 和**普通对话**。本地命令行、stdio MCP server、Agent Skill。全程本地，无需 API key。只读取已有历史，不发送新对话。

每个 Bot 保存名单、完整记录和附件。普通对话写到另一个目录。[OpenCode](https://opencode.ai)、Claude Code、Codex 等可通过 MCP server 和 Skill 查询 Bot 归档。

[特性](#特性) · [快速开始](#快速开始) · [教程](#教程) · [MCP](#mcp) · [Agent skills](#agent-skills) · [输出布局](#输出布局) · [联系](#联系) · [捐赠](#捐赠)

## 特性

- **命令行。** `grok-bot-export.py` 可导出 Bot、普通对话，或两者（`--mode bot`、`--mode chat`、`--mode all`）。`--messages-only` 跳过 Bot 附件下载。
- **Grok Bot。** 名单、完整记录、附件（图片、视频和其他文件），按 4 MB 分块并行下载。
- **普通对话。** 每个会话一份 Markdown、一份原始 JSON，外加一份合并的 JSONL。
- **归档。** JSONL、可读 Markdown、原始 JSON，以及索引。
- **MCP。** 仅标准库的 stdio server：`list_bots`、`get_bot`、`search`。只读取 Bot 归档。
- **Skill。** `.claude/skills/grok-export/`：Claude Code、OpenCode，以及其他加载该目录的 Agent 可用。

Bot 历史走 grok.com 的 Bot WebSocket。普通对话走 grok.com 的 app-chat HTTP API；返回 HTTP 429 时会重试。MCP 不索引普通对话导出。打开导出文件，或把目录交给 Agent。

## 快速开始

```bash
git clone https://github.com/LofiSu/grok-export-tool.git
cd grok-export-tool
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Python 3.9 或更高。依赖：`websocket-client`、`cryptography`（[requirements.txt](requirements.txt)）。Windows 自动解密 cookie 另需 `pywin32`。MCP server 只用标准库。

```bash
python3 grok-bot-export.py                  # Grok Bot：消息和附件
python3 grok-bot-export.py --messages-only  # Grok Bot：只要文字
python3 grok-bot-export.py --mode chat      # 普通 Grok 对话
python3 grok-bot-export.py --mode all       # 两者都导出
```

对应脚本：`./export.sh`、`./export-messages.sh`、`./export-chat.sh`。

| 平台 | Cookie 登录 |
| --- | --- |
| macOS | 钥匙串项目 **Chrome Safe Storage**。扫描 Default、Profile 1、Profile 2。 |
| Windows | 已安装 `pywin32` 时用 DPAPI。App-Bound Encryption 需 `--cookie`。 |
| Linux | 只尝试旧版固定密钥或明文。失败时用 `--cookie`。 |

```bash
python3 grok-bot-export.py --cookie "sso=...; sso-rw=..."
```

从自己浏览器的 DevTools 复制 `sso` 和 `sso-rw`。不要把这些值贴进 issue、聊天或 git。

进度日志是中文。未指定目录时，文件写到 `~/Downloads/`。步骤见[教程](#教程)。

## 教程

同一份教程，中英都有，网站和仓库里各一份：安装、各导出模式、归档、MCP、Skill、故障排除。

- **网站：** [lofisu.github.io/grok-export-tool](https://lofisu.github.io/grok-export-tool/) · [中文首页](https://lofisu.github.io/grok-export-tool/index.zh-CN.html)
- **中文：** [docs/guide.zh-CN.md](docs/guide.zh-CN.md) · [网站上的教程](https://lofisu.github.io/grok-export-tool/guide.zh-CN.html)
- **English：** [docs/guide.md](docs/guide.md) · [on the site](https://lofisu.github.io/grok-export-tool/guide.html)

## MCP

`grok-bot-mcp.py` 通过 stdio 提供 MCP，不访问网络。传入 **Bot** 导出目录。省略路径时，选用 `~/Downloads/grok-bot-export-*` 里修改时间最新的目录。

OpenCode 当前的配置把服务器写在 `mcp.servers` 下。编辑 `~/.config/opencode/opencode.json`（或项目里的 `opencode.json`）：

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
| `get_bot` | 按名称、id 片段，或 `01` 这样的目录前缀取一个 bot。`limit` 默认 200 |
| `search` | 在消息正文里做区分大小写的子串搜索，并带上相邻消息。`context` 默认 2 |

Claude Code、Codex、Cursor 用各自的配置启动同一进程。路径和示例见[教程](docs/guide.zh-CN.md#6-opencode-的-mcp-server)。

## Agent skills

Skill 在 `.claude/skills/grok-export/SKILL.md`，名称是 **grok-export**。

- **Claude Code** 读取项目里的 `.claude/skills/`。
- **OpenCode** 也读取该目录，或在配置里写 `"skills": [".claude/skills"]`。
- **Codex、Copilot、Gemini CLI、Cursor**：按各自文档，把 `grok-export/` 拷到它们的 skills 目录。

向 Agent 说明要导出，或要在 Bot 归档里查什么。

## 输出布局

Grok Bot（默认，或 `--mode all` 的 Bot 部分）：

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

`messages.jsonl` 每行一个 JSON。字段：`seq`、`type`（`message`、`send-message`、`user-attachment`、`event`、`voice-call`）、`role`（有角色时为 `user` 或 `assistant`）、`content`、`timestamp`、`timestampMs`、`attachment`、`localFile`、`event`、`call`。

普通对话（`--mode chat`，或 `--mode all` 的对话部分）：

```
~/Downloads/grok-chat-export-YYYYMMDD/
  _index.md
  conversations.jsonl
  conversations/
    0001_<标题>.md
    0001_<标题>.json
```

`conversations.jsonl` 的字段：`conversationId`、`title`、`role`、`sender`、`content`、`timestamp`、`timestampMs`。保存回复文本和原始 JSON，不下载附件文件。

第一个参数可指定输出目录。`--mode all` 且指定了目录时，Bot 写入该目录，普通对话写入同一路径并追加 `-chat`。umask 为 077，目录 `0700`，文件 `0600`。已存在且非空的附件会跳过。`--workers` 默认 6（允许 1–32），只用于 Bot 附件。`--messages-only` 是 `--skip-attachments` 的别名，只影响 Bot。

先看 `_index.md`。读某个 Bot 时打开 `conversation.md` 或 `messages.jsonl`。Bot 导出里的 `AGENTS.md` 是给 Agent 的简短目录说明。

## 免责声明

社区在公开仓库里维护，不是 xAI 发布的。grok.com 的接口可能随时变更。只备份自己的账号，并遵守 grok.com 的条款。导出目录视为私密。漏洞请私下报告，不要附带 cookie 或对话内容，见 [SECURITY.md](SECURITY.md)。

## 联系

使用问题、文档修改、平台适配：

- GitHub：[github.com/LofiSu](https://github.com/LofiSu)
- X：[X / @su_lofi](https://x.com/su_lofi)
- 邮箱：[lofisuchat@gmail.com](mailto:lofisuchat@gmail.com)

## 捐赠

可通过 GitHub Sponsors 赞助，或发邮件。

- [GitHub Sponsors](https://github.com/sponsors/LofiSu)
- 邮件：[lofisuchat@gmail.com](mailto:lofisuchat@gmail.com)

## 许可证

[MIT](LICENSE)
