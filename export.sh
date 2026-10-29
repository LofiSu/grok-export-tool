#!/bin/bash
# 完整导出：对话消息 + 多模态附件
cd "$(dirname "$0")"
exec python3 grok-bot-export.py "$@"
