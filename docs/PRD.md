# dot-skill Product Requirements Document v2.0

## 1. Overview

dot-skill is a meta-skill that turns source material and user descriptions into independently runnable AI Skills.

A generated Skill contains two parts:

- **Part A: Work Skill** captures technical ability, working method, domain knowledge, and output preferences.
- **Part B: Persona** captures personality, communication style, decision patterns, and interpersonal behavior.

The two parts can run together or separately. A generated Skill can evolve through additional files or correction messages.

## 2. User Flow

1. The user launches `/dot-skill`.
2. The system asks which character family to create: `colleague`, `relationship`, or `celebrity`.
3. The user provides optional profile fields such as name, company, level, role, gender, MBTI, tags, and subjective impression.
4. The user imports source material such as PDFs, Feishu links, exported messages, email files, screenshots, meeting notes, Markdown, or pasted text.
5. The system analyzes work capability and persona signals separately.
6. The system previews Work Skill and Persona summaries.
7. After confirmation, the writer creates artifacts under `./skills/{character}/{slug}/`.
8. Future files and correction messages merge into the right layer and are versioned.

## 3. Input Schema

```yaml
name: required display name or alias
company: optional company name
level: optional level such as L6 or P7
role: optional role such as Backend Engineer or Product Manager
gender: optional
mbti: optional
personality: []
culture: []
impression: optional free-text impression
character: colleague | relationship | celebrity
classification:
  language: en
```

Preserve these keys as machine-readable fields. Translate example values into English unless a locale-specific behavior is being tested.

## 4. Source Types

| Source | Format | Processing | Target layer |
|--------|--------|------------|--------------|
| Technical docs | `.pdf`, `.md`, pasted text | Text extraction | Work Skill |
| API design docs | `.pdf`, `.md` | Text extraction | Work Skill |
| Code standards | `.md`, `.txt` | Text parser | Work Skill |
| Feishu Wiki | Exported PDF/Markdown or link | Feishu collector | Work Skill and Persona |
| Feishu messages | `.json`, `.txt`, API | Message parser | Mostly Persona |
| DingTalk messages/docs | Browser/API collection | DingTalk collector | Work Skill and Persona |
| Slack messages | API | Slack collector | Mostly Persona |
| Email | `.eml`, `.mbox`, `.txt` | Email parser | Persona and Work Skill |
| Meeting notes | `.pdf`, `.md`, pasted text | Text extraction | Persona and Work Skill |
| Screenshots | `.jpg`, `.png` | Image-capable host | Either layer |
| Word docs | `.docx` | Optional conversion | Converted text |
| Excel files | `.xlsx` | Optional CSV conversion | Converted table text |

Source priority:

1. Long-form writing authored by the subject.
2. Decision replies such as approvals, rejections, design reviews, and tradeoff comments.
3. Review comments on other people's work.
4. Daily communication.

## 5. Generated Content

### Work Skill

Extract:

- owned systems, business areas, and responsibility boundaries
- technical standards and implementation preferences
- workflow for requirements, design docs, coding, review, debugging, and release
- output templates and preferred formats
- reusable domain knowledge and constraints

The Work Skill must be executable: it should help complete tasks, not merely describe the person.

### Persona

Extract:

- hard behavioral rules
- identity and self-positioning
- expression style and rhythm
- decision heuristics
- interpersonal patterns
- correction rules from user feedback

Persona rules shape tone and task acceptance. Layer 0 safety and identity rules always take priority.

## 6. Artifacts

Each generated Skill writes:

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

Generated Skills live under:

```text
./skills/colleague/{slug}/
./skills/relationship/{slug}/
./skills/celebrity/{slug}/
```

## 7. Evolution

New source material should be merged without overwriting established conclusions unless the new evidence is explicit and stronger. Correction messages should be appended to a correction log and reflected immediately in generated behavior.

Every update archives the previous version under `versions/` and increments the version metadata.

## 8. Host Compatibility

The canonical entrypoint is `/dot-skill`. Generated Skills use:

```text
/{character}-{slug}
/{character}-{slug}-work
/{character}-{slug}-persona
```

The supported hosts are Claude Code, Hermes Agent, OpenClaw, and Codex.

## 9. Non-Goals

- Do not require all profile fields.
- Do not require a single source platform.
- Do not store private credentials in generated artifacts.
- Do not make the Skill impersonate a real person for deception or unsafe use.
