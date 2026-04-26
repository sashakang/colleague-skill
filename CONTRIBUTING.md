# Contributing to dot-skill

Thanks for contributing. dot-skill distills a person, relationship, or public figure into an AI Skill. The project improves when contributors add collectors, improve prompts, test host compatibility, and document real workflows.

## Ways to Contribute

- Fix bugs in the Python tools, installers, prompt pipeline, or tests.
- Improve docs, examples, or host setup instructions.
- Add or harden data collectors for Feishu, DingTalk, Slack, email, WeChat exports, and future sources.
- Submit generated Skills or gallery metadata.
- Test on Windows, macOS, Linux, Claude Code, Hermes, OpenClaw, and Codex.

## Development Setup

```bash
git clone https://github.com/titanwings/colleague-skill
cd colleague-skill
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional collectors may require extra dependencies such as `playwright`, `python-docx`, `openpyxl`, Node.js, or a platform-specific token.

## Branch and PR Workflow

1. Create a focused branch for one change.
2. Keep generated data, credentials, logs, and private exports out of commits.
3. Add or update tests when behavior changes.
4. Run the most relevant test subset before opening a PR.
5. In the PR description, include what changed, how it was tested, and any migration notes.

## Commit Style

Use short imperative commits:

```text
fix: preserve codex generated-skill installer paths
docs: clarify Slack auto-collection setup
test: cover relationship skill manifest fields
```

## Code Style

- Prefer small, explicit Python functions.
- Preserve existing CLI flags, JSON/YAML keys, file paths, and output schemas unless a migration is intentional.
- Do not commit secrets or private source material.
- Keep prompts deterministic enough that generated artifacts remain reviewable.
- Keep docs and examples in English.

## Tests

Useful targeted commands:

```bash
python -m unittest tests.test_skill_entrypoint_docs
python -m unittest tests.test_skill_writer
python -m unittest tests.test_research_tools
python -m unittest discover -s tests -p 'test_*.py'
```

## Security

Never include real tokens, cookies, private chat exports, private emails, or internal documents in issues, PRs, examples, or tests. Redact names and sensitive content in fixtures.

## Documentation

When changing install behavior, update `README.md`, `INSTALL.md`, and `SKILL.md` together. When changing generated artifact structure, update tests and sample Skills under `skills/colleague/`.

## Community

Use GitHub Issues for bugs and GitHub Discussions or Discord for product ideas and design discussion.

## License

By contributing, you agree that your contribution is licensed under the repository's MIT License.
