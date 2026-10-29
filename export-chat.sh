#!/bin/bash
# 导出普通 Grok 对话（非 Bot 的聊天）
cd "$(dirname "$0")"
exec python3 grok-bot-export.py --mode chat "$@"
