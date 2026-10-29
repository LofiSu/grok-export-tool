# grok-export-tool

把你在 [grok.com](https://grok.com) 上的**全部 Grok Bot 数据**导出——所有对话 + 多模态附件（图片、视频、文件）——整理成**利于 AI Agent 理解**的格式，并提供轻量 **MCP server** 和 **Agent Skill**，让 Codex / Claude Code / OpenCode 等 Agent 直接查询上下文。

> 全程本地完成。无需浏览器插件、无需重新登录、无需 API Key，也**不受消息额度限制**——它通过 grok.com 内部 WebSocket 接口读取历史，带的是你本机 Chrome 已登录的 cookie。

## 特性

- 📦 导出账号下所有 Grok Bot（名单 + 完整对话历史）
- 🖼️ 并行下载多模态附件（图片/视频/文件），4MB 大分块
- 🧠 输出 Agent 友好的结构（归一化 `messages.jsonl` + 可读 `conversation.md` + 原始 `transcript.json`）
- 🔌 轻量零依赖 MCP server（`list_bots` / `get_bot` / `search`）
- ⚡ 附带标准 Agent Skill（SKILL.md，27+ Agent 支持），一键接入导出+查询工作流

## 平台支持

| 平台 | Cookie 鉴权 |
| --- | --- |
| **macOS** | 通过钥匙串（"Chrome Safe Storage"）自动解密。 |
| **Windows** | 通过 DPAPI 自动解密（`pip install pywin32`）；若 Chrome 使用 App-Bound 加密，请用 `--cookie`。 |
| **Linux** | 尽力而为（老版本 "peanuts" 密钥 / 明文）；否则用 `--cookie`。 |

任何平台的通用回退：

```bash
python3 grok-bot-export.py --cookie "sso=...; sso-rw=..."
```

（从浏览器 DevTools → Application → Cookies → grok.com 复制 `sso` 和 `sso-rw` 的值。）

需要 Python 3.9+。

## 安装

```bash
pip install -r requirements.txt
```

## 用法

```bash
# Grok Bot（默认）：完整导出（消息 + 附件）
python3 grok-bot-export.py

# Grok Bot：仅消息（约 20 秒）
python3 grok-bot-export.py --messages-only

# 普通 Grok 对话（非 Bot 的聊天）
python3 grok-bot-export.py --mode chat

# Bot 和普通对话都导出
python3 grok-bot-export.py --mode all
```

默认输出到 `~/Downloads/grok-bot-export-YYYYMMDD/`（chat 模式为 `~/Downloads/grok-chat-export-YYYYMMDD/`），可在命令后加自定义目录。附件下载是幂等的——已下载的文件在重跑时会跳过。

## 输出结构

```
grok-bot-export-YYYYMMDD/
  AGENTS.md               ← Agent 使用说明（建议先读）
  _index.md               全部 bot 索引
  roster.json             机器可读的 bot 名单
  01_<bot名>/
    meta.json             bot 元数据（name / agentId / status / lastTurnAt）
    transcript.json       原始完整数据（保底）
    messages.jsonl        ★ 归一化消息流（每行一条 JSON）
    conversation.md       可读对话（角色清晰）
    attachments/          多模态文件
```

`messages.jsonl` 每行统一 schema：`seq`、`type`、`role`（user/assistant）、`content`、`timestamp`、`attachment`、`localFile`、`event`、`call`。

## MCP server 接入

`grok-bot-mcp.py` 是 stdio 协议的零依赖 MCP server。配置示例：

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

工具：`list_bots`、`get_bot`（bot 名 + limit）、`search`（关键词 + 上下文）。

## 支持的 Agent

导出的数据 + MCP server 可被任何支持 MCP 的 Agent（或直接读文件）消费：

**本地 Agent（stdio MCP 直接可用）：**

- **Codex**（OpenAI）—— 加入 `~/.codex/config.toml` 或 `codex mcp add`
- **Claude Code**（Anthropic）—— `claude mcp add grok-bot -- python3 /path/to/grok-bot-mcp.py /path/to/export`
- **OpenCode** —— 用 MCP（`grok-bot`）或自带 **skill**（`grok-export`）
- **Cursor** —— Cursor Settings → MCP 里添加
- **Windsurf、Cline、Roo Code、Kilo Code、Zed、GitHub Copilot** 等任何支持 MCP 的 Agent，配置方式相同

**云端 Agent（需要远程 MCP 端点）：**

- **Grok Bot** —— 运行在 xAI 的云 VM 上，无法直接访问你本地的 stdio 进程。它本身支持 MCP，但只支持**公开可达的 MCP server（HTTP）**。要让 Grok Bot 查询数据，需要把 `grok-bot-mcp.py` 部署成 HTTP MCP（或把导出的文件放到 Grok Bot 能读取的地方）。

**没有 MCP？** 直接把导出的文件夹交给 Agent——先读 `AGENTS.md`，再读每个 bot 的 `messages.jsonl` / `conversation.md`。

## Agent Skills 接入

仓库自带一个符合 [Agent Skills](https://agentskills.io) 开放标准的 skill：`.claude/skills/grok-export/SKILL.md`。该标准被 **27+ 个 Agent** 支持，包括 Claude Code、Codex、GitHub Copilot、Gemini CLI、OpenCode、Cursor 等。

安装方式：把 Agent 指向该 skill 目录，或把 `grok-export/` 复制到该 Agent 自己的 skills 目录：

- **Claude Code** —— 自动读取项目里的 `.claude/skills/`
- **OpenCode** —— 自动读取 `.claude/skills/`（项目兼容），或在配置里加 `"skills": ["…/.claude/skills"]`
- **Codex / Copilot / Gemini CLI / Cursor** —— 把 `grok-export/` 复制到对应 Agent 的 skills 目录（见其文档）

配置好后，直接说「帮我导出 Grok Bot 数据」或 `@grok-export`，Agent 会按 skill 流程执行。

## 工作原理

1. 从本机 Chrome cookie 数据库解密出 `sso`/`sso-rw`（macOS 钥匙串 / Windows DPAPI / `--cookie`）。
2. 连接 `wss://grok.com/ws/bot/`（JSON-RPC over WebSocket）。
3. `bot.roster` 列出所有 bot；`bot.transcript.offbox` 分页拉取每个 bot 的历史。
4. 附件通过 `bot.command` + `readAttachmentChunk` 以 4MB 分块下载。
5. 归一化成 Agent 友好的结构。

## 免责声明

这是一个**非官方**工具，与 xAI 无关。它依赖逆向的内部接口，可能随时失效。仅用于备份你自己的账号数据，并请遵守 grok.com 的服务条款。

## License

[MIT](LICENSE)
