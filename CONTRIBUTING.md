# Contributing to grok-export-tool

Thanks for your interest in contributing! This is a small, dependency-light tool, so most contributions fall into a few buckets.

## Scope

- **Bug fixes** — especially around the reverse-engineered endpoints (they can change without notice).
- **New message/entry kinds** — Grok Bot transcripts have several `entryKind` values; adding clean handling for new ones is welcome.
- **Platform support** — currently macOS + Chrome only. Help with Windows/Linux cookie decryption or browser support.
- **Documentation** — English and Chinese READMEs, `docs/guide.md`, `docs/guide.zh-CN.md`, and the Pages site in `docs/`.

## Setup

```bash
git clone https://github.com/LofiSu/grok-export-tool.git
cd grok-export-tool
pip install -r requirements.txt
```

## Conventions

- Keep the tool dependency-light. The only runtime deps are `websocket-client` and `cryptography`.
- Keep the MCP server (`grok-bot-mcp.py`) zero-dependency (stdlib only).
- Preserve the Agent-friendly output schema in `messages.jsonl` when adding fields.

## Before submitting

- Make sure `python3 -c "import ast; ast.parse(open('grok-bot-export.py').read())"` passes.
- Don't commit any personal data (agent IDs, cookies, exported output).

## Code of conduct

Be kind and respectful. No personal data in issues or PRs.
