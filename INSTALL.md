# dot-skill Installation Guide

dot-skill follows the [AgentSkills](https://agentskills.io) layout. The repository itself is the skill directory.

## Supported Hosts

Compatible hosts:

- Claude Code
- Hermes Agent
- OpenClaw
- Codex

Use `/dot-skill` as the stable entrypoint in slash-command hosts. Compatibility remains for the `colleague`, `relationship`, and `celebrity` families at the tooling and storage layers, but new workflows should use `/dot-skill`.

## Claude Code

Install into the current project:

```bash
git clone https://github.com/titanwings/colleague-skill .claude/skills/dot-skill
```

Install globally:

```bash
git clone https://github.com/titanwings/colleague-skill ~/.claude/skills/dot-skill
```

Launch with:

```text
/dot-skill
```

Generated character Skills can be installed with:

```bash
python3 tools/install_claude_generated_skill.py --skill-dir ./skills/colleague/<slug>
```

Windows Claude installations also write `~/.claude/commands/{character}-{slug}.md` so generated slash commands remain discoverable.

## OpenClaw

Install this repository:

```bash
git clone https://github.com/titanwings/colleague-skill ~/.openclaw/workspace/skills/dot-skill
```

Or from an existing checkout:

```bash
python3 tools/install_openclaw_skill.py --force
```

Generated character Skills can be installed with:

```bash
python3 tools/install_openclaw_generated_skill.py --skill-dir ./skills/colleague/<slug>
```

## Hermes

Install from an existing checkout:

```bash
python3 tools/install_hermes_skill.py --force
```

Then start a new Hermes session and run:

```text
/dot-skill
```

## Codex

Install this repository:

```bash
git clone https://github.com/titanwings/colleague-skill ~/.codex/skills/dot-skill
```

Or from an existing checkout:

```bash
python3 tools/install_codex_skill.py --force
```

Codex does not require a slash command. After installation it discovers `dot-skill` as a local skill. Generated character Skills are installed under `~/.codex/skills/` and can be invoked by skill name.

Generated character Skills can be installed with:

```bash
python3 tools/install_codex_generated_skill.py --skill-dir ./skills/colleague/<slug>
```

## Generated Skill Layout

Generated Skills are written by character family:

```text
./skills/colleague/{slug}/
./skills/relationship/{slug}/
./skills/celebrity/{slug}/
```

Each generated Skill includes:

```text
SKILL.md
work.md
persona.md
work_skill.md
persona_skill.md
meta.json
manifest.json
versions/
knowledge/
```

In slash-command hosts, generated Skills use:

```text
/{character}-{slug}
/{character}-{slug}-work
/{character}-{slug}-persona
```

## Dependencies

Base runtime:

```bash
pip3 install -r requirements.txt
```

Optional helpers:

```bash
pip3 install pypinyin
pip3 install python-docx
pip3 install openpyxl
pip3 install playwright
playwright install chromium
npm install -g feishu-mcp
```

## Collector Selection

| Scenario | Recommended tool |
|----------|------------------|
| Feishu with App access | `tools/feishu_auto_collector.py` |
| Feishu internal docs without App access | `tools/feishu_browser.py` |
| Manually provided Feishu links | `tools/feishu_mcp_client.py` |
| DingTalk workspace | `tools/dingtalk_auto_collector.py` |
| DingTalk message collection fails | Manual screenshots or exported files |
| Slack workspace | `tools/slack_auto_collector.py` |

## Feishu Auto-Collection

```bash
python3 tools/feishu_auto_collector.py --setup
python3 tools/feishu_auto_collector.py --name "Eulalie" --output-dir ./knowledge/eulalie
python3 tools/feishu_auto_collector.py --name "Eulalie" --msg-limit 500 --doc-limit 20
```

For private chat collection, configure a `user_access_token` and `p2p_chat_id`, or pass them with CLI flags.

## Feishu Browser Collection

```bash
python3 tools/feishu_browser.py --url "https://example.feishu.cn/docx/xxx" --output out.md --show-browser
python3 tools/feishu_browser.py --chat "Backend Team" --target "Eulalie" --limit 500 --output out.txt --show-browser
```

Use `--show-browser` the first time so you can complete login. Later runs can reuse the browser profile.

## Feishu MCP Collection

```bash
python3 tools/feishu_mcp_client.py --setup
python3 tools/feishu_mcp_client.py --url "https://example.feishu.cn/docx/xxx" --output out.md
python3 tools/feishu_mcp_client.py --chat-id "oc_xxx" --target "Eulalie" --output out.txt
```

## DingTalk Auto-Collection

```bash
python3 tools/dingtalk_auto_collector.py --setup --show-browser
python3 tools/dingtalk_auto_collector.py --name "Eulalie" --output-dir ./knowledge/eulalie
```

## Slack Auto-Collection

Create a Slack App at `https://api.slack.com/apps`, install it to the workspace, invite the bot to target channels, then run:

```bash
python3 tools/slack_auto_collector.py --setup
python3 tools/slack_auto_collector.py --name "eulalie" --output-dir ./knowledge/eulalie
python3 tools/slack_auto_collector.py --name "eulalie" --msg-limit 500 --channel-limit 20
```

Required Bot Token scopes:

| Scope | Purpose |
|-------|---------|
| `users:read` | Search users |
| `channels:read` | List public channels |
| `channels:history` | Read public channel history |
| `groups:read` | List private channels |
| `groups:history` | Read private channel history |
| `mpim:read` | Optional group DM list |
| `mpim:history` | Optional group DM history |
| `im:read` | Optional DM list |
| `im:history` | Optional DM history |

Free Slack workspaces expose only the most recent 90 days of message history.

Common Slack errors:

| Error | Cause | Fix |
|-------|-------|-----|
| `missing_scope: channels:history` | Missing Bot Token scope | Add the scope and reinstall the App |
| `invalid_auth` | Token is invalid or revoked | Run `--setup` again |
| `not_in_channel` | Bot is not in the channel | Invite the bot with `/invite @bot` |
| User not found | Name does not match Slack metadata | Use username, display name, or email |
| 90-day history only | Free workspace limit | Upgrade Slack or add manual source material |
| Rate limit `429` | Too many requests | The script waits and retries automatically |

## Verification

From the repository root or installed skill directory:

```bash
python -m unittest tests.test_install_hermes_skill
python -m unittest tests.test_install_openclaw_and_codex
python -m unittest tests.test_install_claude_generated_skill
python -m unittest tests.test_research_tools
python3 tools/skill_writer.py --action list --character colleague --base-dir ./skills/colleague
```
