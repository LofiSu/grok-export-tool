# Security Policy

## Supported versions

This is a local, unofficial backup tool. Security fixes land on the default branch (`main`). There are no versioned releases yet.

| Version | Supported |
| --- | --- |
| `main` | Yes |

## Reporting a vulnerability

Report suspected vulnerabilities in private. Do not open a public GitHub issue for security reports.

- Preferred: [GitHub private vulnerability reporting](https://github.com/LofiSu/grok-export-tool/security/advisories/new), once the repository allows it.
- Until private reporting is enabled, contact the repository owner directly and ask them to open a private advisory.

Include a description of the impact, the files involved, and the `main` commit SHA you tested. Reproduction steps must not depend on a real grok.com account.

Do not include any of the following in a report, pull request, or issue:

- Chrome cookies, `sso` / `sso-rw` values, or copies of the cookie database
- The macOS Keychain "Chrome Safe Storage" password, or any key derived from it
- Exported conversations, attachments, agent IDs, or other personal Grok Bot data
- Credentials, session tokens, or environment files

If a proof of concept needs a fixture, use synthetic values and a throwaway directory.

Please allow time for a fix before any public write-up.

## Scope

In scope:

- Local handling of Chrome cookie material used to read your own grok.com session
- Files the exporter writes, including accidental inclusion of session material in logs or archives
- The stdio MCP server (`grok-bot-mcp.py`) when pointed at an export directory
- Repository and CI configuration that could leak secrets

Out of scope:

- grok.com, xAI, or Google Chrome themselves
- Use of this tool against an account you do not own
- Social engineering or physical access to an unlocked machine

## Safe use

- Run the exporter only on a machine where you are already logged into your own grok.com account.
- Treat `~/Downloads/grok-bot-export-*` as private. An export can contain full transcripts and attachments.
- Do not commit export output, cookie databases, or Keychain material. Export folders are written outside the repository by default.
- `grok-bot-mcp.py` does not open a network connection. Pass it only an export directory you trust.
- Cookie decryption exists so the tool can reuse an existing local Chrome login. Keep that material on the machine. It does not belong in logs, issues, or git history.
