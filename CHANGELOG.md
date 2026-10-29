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

### Chat export

- `grok-bot-export.py` on `main` exports regular Grok chats with `--mode chat` and both products with `--mode all` (`export-chat.sh`). Chat output is a separate directory (`~/Downloads/grok-chat-export-YYYYMMDD/`). The MCP server still indexes Grok Bot folders only.

### Packaging

- Rewrote `README.md` and `README.zh-CN.md`: bilingual switch, text poster placeholder, features, quick start, tutorial links, MCP, output layout for Bots and regular chats, disclaimer, contact, and donate.
- Added `docs/guide.md` and `docs/guide.zh-CN.md`, and a GitHub Pages site under `docs/` (`index.html`, `index.zh-CN.html`, `guide.html`, `guide.zh-CN.html`). The poster slot is text until an approved image is added at `docs/assets/poster.png`.
- Added `.github/workflows/pages.yml` to deploy `docs/` to GitHub Pages on push to `main`. The Pages URL is `https://lofisu.github.io/grok-export-tool/` after the repository source is set to GitHub Actions.
- Pointed `REPO_META.md` at that website and refreshed the description and topics. About text, topics, and the Pages source still need a manual save on GitHub.
- Updated `llms.txt` for chat mode, the guides, and the site. Smoke CI also syntax-checks `export-chat.sh`.
