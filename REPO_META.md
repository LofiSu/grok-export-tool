# Repository metadata

Suggestions for the GitHub About box. Nothing in this file is applied automatically. Description, website, and topics still need a manual save on the GitHub website.

## Description

Use this text (162 characters; GitHub allows 350):

> Local exporter for your own Grok Bots and regular Grok chats. No API key. Writes a JSONL and Markdown archive, with a zero-dependency MCP server and agent skills.

Shorter alternative (76 characters):

> Export Grok Bots and chats locally. MCP server and agent skills. No API key.

The About text should stay a description of a personal backup tool: Bots and chats, local, no API key, MCP, and skills.

## Topics

Apply these as GitHub repository topics:

- `grok`
- `grok-bot`
- `mcp`
- `model-context-protocol`
- `python`
- `data-export`
- `backup`
- `ai-agents`
- `opencode`
- `websocket`
- `chrome`
- `xai`
- `jsonl`
- `github-pages`

## Website

Set the About website field to:

https://lofisu.github.io/grok-export-tool/

That is the GitHub Pages URL for user `LofiSu` (Pages hostnames are lowercase). The site is the static files in `docs/`. It will answer only after both of these are true:

1. This repository’s Pages source is **GitHub Actions** (Settings → Pages → Build and deployment → Source).
2. `.github/workflows/pages.yml` has run on `main` and the deployment succeeded.

Until then the URL 404s. The README is the page that works as soon as the repository is public.

## Still needs a click on GitHub

- Paste the description above into the About box.
- Paste the website URL above.
- Apply the topics above. Adding `github-pages` is part of this packaging pass; the rest carry forward.
- Set Pages → Source to **GitHub Actions** once, so the workflow may deploy.
- GitHub Sponsors for `LofiSu` may still be off. The README and the site footer accept sponsorship by email at lofisuchat@gmail.com.
- The approved logo is `docs/assets/logo.png` (same bytes as `docs/assets/grok-bot-logo.png`). The poster is `docs/assets/poster.png`.

## Before making the repository public

- Default branch is `main`. The license is MIT (`LICENSE`).
- Link `SECURITY.md` from the repository security policy.
- Do not publish sample exports, cookies, cookie databases, or screenshots of private transcripts.
- The project is not affiliated with xAI or grok.com.
