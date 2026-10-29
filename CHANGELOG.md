# Changelog

All notable changes to this project are documented in this file.

This project does not assign version numbers yet. Entries are grouped by calendar day on `main`.

## 2026-10-29

### Initial

- Added `grok-bot-export.py` to export every Grok Bot visible to the local Chrome session: roster, full transcripts, and multimodal attachments.
- Added a zero-dependency stdio MCP server, `grok-bot-mcp.py`, with `list_bots`, `get_bot`, and `search`.
- Added `export.sh`, `export-messages.sh`, and `requirements.txt` (`websocket-client`, `cryptography`).
- Licensed the project under MIT.

### Docs

- Added English and Chinese READMEs, `llms.txt`, the OpenCode skill at `.opencode/skills/grok-export/`, and `CONTRIBUTING.md`.
- Added `SECURITY.md` for private vulnerability reports. Reports must not include cookies, key material, or exported conversations.
- Added `.github/workflows/ci.yml`: MIT license check, byte-compile, shell syntax, export `--help`, and an MCP initialize / `tools/list` dry-run against an empty directory.
- Added `REPO_META.md` with a suggested public description and topics.
