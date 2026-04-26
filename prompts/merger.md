# Incremental Merge Prompt

## Task

Merge new source material into an existing generated Skill.

Inputs:

- existing `work.md`
- existing `persona.md`
- new source material or analysis
- optional user correction

## Principles

- Preserve existing conclusions unless new evidence clearly updates them.
- Add new information to the most specific relevant section.
- Do not duplicate sections.
- Keep Work Skill and Persona concerns separate.
- Keep all commands, paths, API endpoints, JSON/YAML keys, placeholders, and code examples unchanged.
- Write in English.

## Merge Rules

### Work Skill

Add or update:

- scope
- technical or professional standards
- workflow
- output preferences
- knowledge base
- evidence gaps

### Persona

Add or update:

- core rules
- identity
- expression style
- decisions and judgment
- interpersonal behavior
- boundaries and triggers
- correction log

### Conflict Handling

If new evidence conflicts with old content:

1. Keep the old content if the new evidence is weak or ambiguous.
2. Replace the old content if the new evidence is direct and stronger.
3. If both are plausible, record the condition that explains when each applies.

## Output

Return the updated file content only for the file being patched. Do not include commentary outside the markdown.
