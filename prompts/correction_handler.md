# Correction Handler Prompt

## Task

Convert user feedback into a precise correction that can be merged into the generated Skill.

Triggered when the user says the Skill misunderstood the person, gives a direct correction, or supplies a better example.

## Input Types

- "They would not say that."
- "They usually do X instead of Y."
- "In this situation, they would ask for evidence first."
- "This work rule is wrong; the team actually uses another process."

## Output Contract

Return one of the writer-compatible patch formats below.

For a Work correction, return a Markdown patch containing one or more complete `##` sections. Each section must be replaceable by `tools/skill_writer.py`.

For a Persona correction, return JSON in one of these shapes:

```json
{"scene": "situation where the correction applies", "wrong": "old behavior or claim", "correct": "correct behavior or claim"}
```

```json
{"persona_corrections": [{"scene": "situation where the correction applies", "wrong": "old behavior or claim", "correct": "correct behavior or claim"}]}
```

If both Work and Persona are affected, return a Work Markdown patch and a separate Persona correction JSON object. Do not invent fields outside these writer-compatible shapes.

## Rules

- Write in English.
- Preserve user-provided commands, paths, API names, and field names exactly.
- Prefer a narrow correction over a broad rewrite.
- If the correction affects voice or behavior, produce a Persona correction JSON object.
- If the correction affects workflow, technical standard, or domain knowledge, produce a Work Markdown patch with complete `##` sections.
- If both layers are affected, produce both outputs separately.
