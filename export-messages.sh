#!/bin/bash
# 纯消息导出（秒出）：只导出对话文字，不下载附件
cd "$(dirname "$0")"
exec python3 grok-bot-export.py --messages-only "$@"
