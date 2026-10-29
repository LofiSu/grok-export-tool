# grok-export-tool 使用教程

[English](guide.md) · [中文](guide.zh-CN.md) · [说明](../README.zh-CN.md)

在 Mac 上，按步骤备份你自己的 [grok.com](https://grok.com) 账号。一条命令里有两块数据：**Grok Bot**（名单、完整记录、附件）和**普通 Grok 对话**。可以只导 Bot、只导普通对话，或两者一起导。

这是非官方工具，是本地备份，不是 xAI 的产品。导出脚本的进度日志本来就是中文。

## 1. 开始之前

下面几项都要满足：

1. 一台 Mac。
2. Google Chrome 已在 [grok.com](https://grok.com) 登录你要备份的账号。Safari、Firefox、Arc、Chromium 都不会被读取。
3. 这个登录位于 Chrome 配置档 **Default**、**Profile 1** 或 **Profile 2**。其他配置档会被忽略。
4. Python 3.9 或更高版本（`python3 --version`）。
5. 账号是你自己的。

Grok Bot 和普通对话是两套东西。Bot 是带 id、名单条目和记录的 agent。普通对话是 grok.com 上的聊天会话。`--mode bot`（默认）导出 Bot。`--mode chat` 导出普通对话。`--mode all` 两者都导出，写到两个目录。

先在 Chrome 里登录，再运行脚本。工具复用这个登录态。它不会弹出登录窗口，也不需要你亲手输入 grok.com 的密码。macOS 会询问一次钥匙串权限，见下文。

## 2. 安装

```bash
git clone https://github.com/LofiSu/grok-export-tool.git
cd grok-export-tool
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

`requirements.txt` 会安装 `websocket-client` 和 `cryptography`。两种模式都需要它们，因为都会先解密 Chrome 的 cookie 数据库。普通对话的请求本身使用 Python 标准库。

跑导出的那个终端要保持虚拟环境处于激活状态。MCP server 没有第三方依赖，它的命令可以用系统自带的 `python3`。

确认命令行：

```bash
python3 grok-bot-export.py --help
```

输出里应有 `--mode {bot,chat,all}`、`--skip-attachments` / `--messages-only` 和 `--workers`。

## 3. 导出

在仓库根目录、虚拟环境已激活时运行。第一次成功读取 cookie 时，macOS 会弹出钥匙串项目 **Chrome Safe Storage** 的对话框。选择**允许**。细节见[故障排除](#7-故障排除)。

### Grok Bot，完整归档

消息、事件、通话记录和附件文件：

```bash
python3 grok-bot-export.py
```

或：

```bash
./export.sh
```

默认目录：`~/Downloads/grok-bot-export-YYYYMMDD/`。

### Grok Bot，只要消息

记录仍然是完整的。附件字节不会下载。记录里如果提到了文件，`messages.jsonl` 仍会写上 `localFile`，之后完整再跑一次时知道该放到哪里。

```bash
python3 grok-bot-export.py --messages-only
```

`--skip-attachments` 是同一个开关。`./export-messages.sh` 是它的包装。

### 普通 Grok 对话

```bash
python3 grok-bot-export.py --mode chat
```

或：

```bash
./export-chat.sh
```

默认目录：`~/Downloads/grok-chat-export-YYYYMMDD/`。

这里写下的是对话文本和原始回复 JSON，不下载附件文件。`--messages-only` 对这一模式没有作用。

### 两者一起

```bash
python3 grok-bot-export.py --mode all
```

不传目录时，Bot 写到 `~/Downloads/grok-bot-export-YYYYMMDD/`，普通对话写到 `~/Downloads/grok-chat-export-YYYYMMDD/`。

没有 `export-all.sh`。`--messages-only` 和 `--mode all` 一起用时，会跳过 Bot 附件，普通对话仍会写出。

### 指定目录

```bash
python3 grok-bot-export.py ~/Backups/grok-bots
python3 grok-bot-export.py --messages-only ~/Backups/grok-bots
python3 grok-bot-export.py --mode chat ~/Backups/grok-chats
python3 grok-bot-export.py --mode all ~/Backups/grok-bots
```

最后一条把 Bot 写到 `~/Backups/grok-bots`，普通对话写到 `~/Backups/grok-bots-chat`。只有在 `--mode all` 并且你传了目录时，才会加上 `-chat` 后缀。只导普通对话时，用的就是你传入的目录，没有后缀。

### 附件线程数

Bot 附件默认 6 个线程。`--workers` 只能是 1 到 32。每个分块 4MB，这是导出器发出的请求大小。

```bash
python3 grok-bot-export.py --workers 4
```

已经存在且不是空文件的附件会留在原地。空文件会重新下载。想补下失败的附件，再跑一次完整的 Bot 导出即可。

### 一次运行覆盖什么

每种模式都会走完当前登录态返回的整份名单。没有只选一个 Bot 或一段对话的开关。导出之后，打开对应文件夹，或让 MCP server 按名字取一个 Bot。

## 4. 文件写到哪里

默认在 `~/Downloads/` 下，位于 git 仓库之外。这是有意的：导出里可能有完整对话和文件，不应该提交进仓库。

cookie 失败时，脚本会在创建目录之前退出。cookie 已经成功、Bot 的 WebSocket 随后失败时，`export_bots` 可能已经建好一个空的输出目录。

## 5. 阅读归档

### Grok Bot

```
grok-bot-export-YYYYMMDD/
  AGENTS.md                 给 Agent 的简短地图；要把文件夹交给 Agent 时先看这个
  _index.md                 每个 Bot 一条链接
  roster.json               接口返回的名单，放在 "agents" 下
  01_<名称>/
    meta.json               该 Bot 的名单记录（name、agentId、status、lastTurnAt，以及记录里的其他字段）
    messages.jsonl          每行一个归一化的 JSON
    conversation.md         同一份记录，带角色，适合人读
    transcript.json         解码后的条目，不依赖归一化结果
    attachments/            下载的文件
```

文件夹序号至少两位（`01`、`02`……）。名称会做清理：路径里不能用的字符会被替换，并截到 60 个字符。

先打开 `_index.md`，再打开某一份 `conversation.md`。写脚本或交给 Agent 时，优先用 `messages.jsonl`。

| 字段 | 含义 |
| --- | --- |
| `seq` | 记录中的顺序 |
| `type` | `message`、`send-message`、`user-attachment`、`event`、`voice-call`，或其他条目类型 |
| `role` | 消息条目上为 `user` 或 `assistant`。`send-message` 记为 `assistant`。`user-attachment` 记为 `user` |
| `content` | 文本。纯用户附件这一条的文本为空 |
| `timestamp`、`timestampMs` | 本地时间字符串，以及原始的毫秒时间 |
| `attachment` | 这条带文件时的文件名和路径 |
| `localFile` | 相对 Bot 文件夹的路径，例如 `attachments/0007_name` |
| `event`、`call` | 对应条目类型的载荷 |
| `entryId`、`fromAgent`、`replyTo`、`messageType`、`raw` | 记录里有这些字段时才会出现 |

`meta.json` 是名单对象本身，不是裁过的 schema。MCP server 展示的是 `name`、`agentId`、`status` 和 `lastTurnAt`。

### 普通对话

```
grok-chat-export-YYYYMMDD/
  _index.md
  conversations.jsonl       所有会话的所有消息，每行一个对象
  conversations/
    0001_<标题>.md          可读记录
    0001_<标题>.json        id、标题、时间，以及原始回复列表
```

序号至少四位。标题的清理方式和 Bot 名称相同。

| `conversations.jsonl` 字段 | 含义 |
| --- | --- |
| `conversationId` | grok.com 的会话 id |
| `title` | 会话标题；接口没给标题时是 `未命名对话` |
| `role` | 发送者是 `human` 时为 `user`，否则为 `assistant` |
| `sender` | 接口返回的发送者字符串 |
| `content` | 消息文本。正文不是字符串时，这里是那段正文的 JSON 文本 |
| `timestamp`、`timestampMs` | 本地时间字符串，以及 `createTime` |

每个会话的 `.json` 保留原始 `messages` 数组，以及 `createTime` 和 `modifyTime`。普通对话导出里没有 `AGENTS.md`，MCP server 也不会索引它。

## 6. OpenCode 的 MCP server

服务器文件是 `grok-bot-mcp.py`。它读取 Grok Bot 目录，并回答三个工具。把第 5 节那个 Bot 文件夹指给它，也就是含有 `roster.json` 和 `01_…` 目录的那一个。

在终端里，这个进程是：

```bash
python3 /absolute/path/to/grok-export-tool/grok-bot-mcp.py \
  /absolute/path/to/grok-bot-export-YYYYMMDD
```

它在 stdin/stdout 上使用 JSON-RPC，并一直等待。日常不用手跑这一行，由 Agent 客户端启动。脚本会展开目录参数里的 `~`。仍然建议写绝对路径，因为有的客户端不会经过 shell。

如果省略目录，服务器按修改时间挑选最新的 `~/Downloads/grok-bot-export-*`。它不会去看 `grok-chat-export-*`。请显式传入 Bot 路径，避免打开的是普通对话目录或一份旧下载。

### OpenCode

当前 OpenCode 配置（`https://opencode.ai/config.json` 上的 schema）使用 `mcp.servers`。编辑全局文件 `~/.config/opencode/opencode.json`，或在项目里新建 `opencode.json`。

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

两条路径都换成你自己的。如果你更想用导出时那个虚拟环境里的 Python，把命令的第一段换成：

```text
/absolute/path/to/grok-export-tool/.venv/bin/python
```

MCP 文件不导入 `websocket` 或 `cryptography`，系统自带的 `python3` 就够。

改完配置后新开一个 OpenCode 会话，让它重新加载。让它使用 `grok-bot` 的工具即可。直接说：先列出 bot，再按你看到的名字打开一个。

| 工具 | 参数 | 行为 |
| --- | --- | --- |
| `list_bots` | 无 | 每个 Bot 一行：名称、`agentId`、消息数、最后活跃时间。措辞是中文 |
| `get_bot` | `bot`（必填），`limit`（默认 200） | 先匹配文件夹前缀（`01`），再匹配名称或 `agentId` 的子串。返回元数据和至多 `limit` 条消息 |
| `search` | `query`（必填），`context`（默认 2） | 在 `content` 里做区分大小写的子串搜索。最多 10 处，并带上相邻消息 |

### 如果 OpenCode 拒绝 `servers`

有些较旧的版本要求服务器直接写在 `mcp` 下面。当前 schema 已把这种写法标为弃用。只有在 `servers` 形式被拒绝时再用：

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

克隆本仓库并把它当作项目打开。OpenCode 会加载 `.opencode/skills/grok-export/SKILL.md`。Skill 名称是 **Grok Export**。用平常的话说要导出，或要在 Bot 归档里查一件事。Skill 会告诉 Agent 该跑哪条命令，并且优先用 MCP，而不是把整份文件贴进提示词。

### 其他 Agent

任何 stdio MCP 客户端都可以启动同一个程序。三种常见写法：

Claude Code，用户范围或项目范围。项目范围是仓库根目录的 `.mcp.json`（Claude Code 询问时再批准）。用户范围在 `~/.claude.json`。两种范围里的 `mcpServers` 对象是同一份 JSON：

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

Codex 读取 `~/.codex/config.toml`（受信任的项目里还可以用 `.codex/config.toml`）：

```toml
[mcp_servers.grok-bot]
command = "python3"
args = [
  "/absolute/path/to/grok-export-tool/grok-bot-mcp.py",
  "/absolute/path/to/grok-bot-export-YYYYMMDD",
]
```

Cursor 使用项目里的 `.cursor/mcp.json`，或 `~/.cursor/mcp.json`：

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

这些客户端会调整自己的文件格式。某个字段被拒绝时，以该产品的 MCP 文档为准；要启动的进程不变。

不要把服务器指到普通对话导出上，然后期待看到 bot。`list_bots` 寻找含有 `meta.json` 的子文件夹。普通对话目录里没有，返回的中文句子会告诉你没有找到导出。

## 7. 故障排除

### 钥匙串提示

导出器会运行：

```text
security find-generic-password -w -s "Chrome Safe Storage" -a Chrome
```

macOS 弹出对话框，询问是否允许访问这个项目。选择允许；若有“始终允许”，之后再跑就不会反复询问。密码留在本机，用来解密 Chrome 的 cookie 数据库。不要把它贴进 issue、聊天或提交。[SECURITY.md](../SECURITY.md) 列出了报告里必须省掉的内容。

如果选了不允许，cookie 解密会失败。脚本以这一行退出：

```text
未能从 Chrome 解密出 grok.com 登录态
```

打开**钥匙串访问**，找到 **Chrome Safe Storage**，允许你正在使用的终端（终端、iTerm，或 IDE 内置终端）。然后重新导出。纯 SSH、没有图形界面的会话可能无法回答这个对话框；先在有图形界面的会话里运行一次。

### Chrome 没有登录

同一行退出信息对应三种原因：

- Google Chrome 里没有登录 grok.com。
- 登录在 Default、Profile 1、Profile 2 以外的配置档。请在这三个之一里登录。这个工具不会再扫描其他配置档。
- 钥匙串被拒绝，cookie 无法解密。

工具需要名为 `sso` 和 `sso-rw` 的两枚 cookie。页面看起来像已登录、但缺其中一枚时，也会同样失败。如果这三个配置档的数据库都不存在，日志里还会有 `未找到 Chrome 的 Default、Profile 1 或 Profile 2 Cookies 文件`。不一定要退出 Chrome；登录是否有效比 Chrome 是否关闭更重要。登录、确认配置档、允许钥匙串，然后再跑。

### Bot 名单为空

日志 `找到 0 个 bot` 表示 WebSocket 名单没有返回 agent。目录仍会写出来：`AGENTS.md`、`_index.md` 和 `roster.json`。

普通对话不是 Bot。它们只出现在 `--mode chat` 或 `--mode all` 的对话目录里。只用 grok.com 主聊天、没有 Bot 的账号，Bot 名单会是空的。

也请确认 Chrome 里是正确的账号。另一个配置档里的第二个 Google 账号，只要不在 Default、Profile 1 或 Profile 2，就是不可见的。

### 普通对话列表为空

`找到 0 个普通会话` 表示列表是空的，或列表请求在拿到任何一页之前就失败了。往上看一行。`会话列表请求失败（HTTP …)` 表示 grok.com 拒绝了列表。HTTP 429 和 HTTP 5xx 会以短退避重试，最多五次。最终失败会停下列表。处理好登录或等一会儿，再跑 `--mode chat`。

某一条标题上的警告（`拉取失败`）表示该会话只保存了当时已经拿到的消息，条数可以是零。同一次运行里的其他会话不受影响。

### Cookie 数据库报错

如果 Python 在复制 Chrome 的 `Cookies` 文件时打出 traceback，请完全退出 Chrome（包括后台进程）再导出。工具把数据库复制到临时文件，读完就删掉。它不会打印 cookie 的值。

### 附件缺失

`--messages-only` 是故意不下载。完整运行时，汇总行会写成功了多少个附件任务。只有下载完成的文件会留下；中断的文件不会被当成已完成。缺文件时再跑一次完整的 Bot 导出。已经不是空文件的会留在原地。超过 2GB 的附件会跳过。

普通对话模式不会写 `attachments/` 文件夹。

### MCP 说没有 bot

传入 Bot 目录，不要传仓库根目录，也不要传普通对话目录。你传入的文件夹里应有带 `meta.json` 的子文件夹。改完路径后重启 Agent 客户端。工具的回复是中文；空结果里会有一句，让你先运行导出并检查目录。

### 跑到 WebSocket 或列表中途停住

grok.com 可能不经通知就改掉这些接口。拉取最新的 `main` 再试。仍然失败的话，开一个 issue，附上错误文本和你运行的 commit。不要附上 cookie、钥匙串密码、agent id 和对话正文。安全问题走 [SECURITY.md](../SECURITY.md)，不要发公开 issue。

## 8. 安全

- 只备份你自己拥有的账号。
- `~/Downloads/grok-bot-export-*` 和 `~/Downloads/grok-chat-export-*` 视为私密。里面可能有完整对话和文件。
- 不要提交导出结果、Chrome 的 cookie 数据库或钥匙串材料。默认输出路径在仓库外面。
- `grok-bot-mcp.py` 不发起网络连接。只把它指到你信任的导出上。导出器本身会用你现有的登录态连接 grok.com，用来读取历史。
- 这个工具不发送新的聊天消息，也不删除 Bot 或会话。
- 解密 cookie 是为了复用已经存在的 Chrome 登录。这些材料留在本机。
- 导出器会把 umask 设为 077，并把导出目录标成目录 `0700`、文件 `0600`。日志里不会出现 cookie 的值。
- 项目与 xAI 无关。请遵守 grok.com 的条款。接口可能会失效。

## 9. 接下来

- [说明](../README.zh-CN.md) · [English README](../README.md)
- 在 `main` 开始发布 GitHub Pages 之后：[项目网站](https://lofisu.github.io/grok-export-tool/)
- [联系与捐赠](../README.zh-CN.md#联系与交流) — GitHub [@LofiSu](https://github.com/LofiSu)、[lofisuchat@gmail.com](mailto:lofisuchat@gmail.com)、[X 上的 Rowan](https://x.com/QiuMilorw)
