[English](README.md) · [中文](README.zh-CN.md)

> **海报待补。** 审核通过的图片会嵌在这里（`docs/assets/poster.png`）。这一版不放生成的占位海报。

# grok-export-tool

把你在 [grok.com](https://grok.com) 上的记录留在自己的电脑上：每一个 **Grok Bot**（含附件），以及**普通 Grok 对话**。Bot 归档按人和 Agent 都好读的方式摆放，再用一个很小的 **MCP server**，让 [OpenCode](https://opencode.ai) 和其他助手回头查询。

非官方。跑在你自己的 Mac 上，用的是已经登录 grok.com 的 Chrome。只备份你自己的账号。

## 特性

- 导出当前 Chrome 登录态能看到的全部 Grok Bot：名单、完整记录、附件（图片、视频和其他文件）。附件按 4MB 分块并行下载。
- 普通 Grok 对话导出到另一个目录：每个会话一份 Markdown、一份原始 JSON，外加一个合并的 JSONL。
- 只想要 Bot 的文字时，可以跳过附件（`--messages-only`）。
- 归档适合 Agent 阅读：归一化 JSONL、可读 Markdown、原始 JSON，以及索引。
- 附带零第三方依赖的 stdio MCP server（`list_bots`、`get_bot`、`search`），查询的是 **Bot** 归档。
- 仓库里带有 OpenCode skill：`.opencode/skills/grok-export/`，覆盖导出和查询。

导出的是你已经有的历史。它不发送新对话，也不删除数据。Bot 历史走 grok.com 的 Bot WebSocket。普通对话走 grok.com 的 app-chat HTTP 接口；这个接口可能返回 HTTP 429，脚本会重试。

目前只有 macOS + Google Chrome。会查看的配置档是 Default、Profile 1 和 Profile 2。MCP server 读取 Grok Bot 导出目录。普通对话导出是你自己打开的文件。

## 快速开始

```bash
git clone https://github.com/LofiSu/grok-export-tool.git
cd grok-export-tool
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

需要 Python 3.9 或更高版本。依赖是 `websocket-client` 和 `cryptography`（[requirements.txt](requirements.txt)）。MCP server 只用标准库，所以即使用虚拟环境跑导出，MCP 仍可以用系统自带的 `python3`。

```bash
python3 grok-bot-export.py                  # Grok Bot：消息和附件
python3 grok-bot-export.py --messages-only  # Grok Bot：只要文字
python3 grok-bot-export.py --mode chat      # 普通 Grok 对话
python3 grok-bot-export.py --mode all       # 两者都导出
```

三个入口也可以写成 `./export.sh`、`./export-messages.sh`、`./export-chat.sh`。

第一次运行时，macOS 会询问钥匙串项目 **Chrome Safe Storage**。选择允许。进度日志是中文。未指定目录时，文件写到 `~/Downloads/`。

[使用教程](docs/guide.zh-CN.md) 按步骤写了安装、每种导出、如何阅读归档、OpenCode，以及真正会遇到的问题（钥匙串、Chrome 未登录、名单为空）。

## 教程

- English：[docs/guide.md](docs/guide.md)
- 中文：[docs/guide.zh-CN.md](docs/guide.zh-CN.md)
- 网站（在 `main` 上启用 GitHub Pages 之后）：[lofisu.github.io/grok-export-tool](https://lofisu.github.io/grok-export-tool/)

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

工具：

| 工具 | 作用 |
| --- | --- |
| `list_bots` | 名称、id、消息数、最后活跃时间 |
| `get_bot` | 按名称、id 片段，或 `01` 这样的文件夹前缀取一个 bot。`limit` 默认 200 |
| `search` | 在消息正文里做区分大小写的子串搜索，并带上相邻消息。`context` 默认 2 |

较旧的 OpenCode 把服务器对象直接放在 `mcp` 下（当前 schema 里这种写法已弃用）。Claude Code、Codex、Cursor 启动的是同一个进程，只是配置文件不同。路径、参数和其他客户端见[教程](docs/guide.zh-CN.md#6-opencode-的-mcp-server)。

在本仓库作为项目打开时，OpenCode 会发现 `.opencode/skills/grok-export/`。Skill 名称是 **Grok Export**。

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

这是非官方工具，与 xAI 无关，也未获其认可。它依赖 grok.com 的接口，这些接口可能随时改变。请只备份你自己拥有的账号，并遵守 grok.com 的条款。导出目录视为私密。漏洞请私下报告，报告中不要包含 cookie 或对话内容，见 [SECURITY.md](SECURITY.md)。

## 联系与交流

欢迎来信，也欢迎一起做。使用上的问题、文档勘误，以及这条 Mac + Chrome 路径之外的平台支持，都可以直接联系。

- GitHub：[github.com/LofiSu](https://github.com/LofiSu)
- 邮箱：[lofisuchat@gmail.com](mailto:lofisuchat@gmail.com)
- X：[x.com/QiuMilorw](https://x.com/QiuMilorw)（Rowan）

## 捐赠

如果这次备份省下了一整个下午，可以通过 [GitHub Sponsors](https://github.com/sponsors/LofiSu) 支持后续维护。若 Sponsors 尚未开通，写一封邮件到 [lofisuchat@gmail.com](mailto:lofisuchat@gmail.com) 即可，邮件捐赠同样欢迎。随缘就好。

## 许可证

[MIT](LICENSE)
