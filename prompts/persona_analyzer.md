# Persona Analysis Prompt

## Task

You will receive source material for **{name}** and optional manual tags.

Extract personality, expression style, decision patterns, interpersonal behavior, boundaries, and correction rules for the Persona layer.

Principles:

- Prefer observed behavior over labels.
- Keep evidence tied to concrete scenes.
- Do not flatten the person into generic adjectives.
- If evidence is missing, write `insufficient source material`.

## Extraction Dimensions

### 1. Hard Behavioral Rules

Identify repeatable rules such as:

- what they do when challenged
- what they do when scope is unclear
- what they refuse or delay
- how they react under deadline pressure
- what always overrides politeness or speed

Write each rule as an executable behavior:

```text
When {situation}, they {action} because {observed reason}.
```

### 2. Identity and Self-Positioning

Extract:

- role identity
- status or expertise posture
- relationship to company culture
- values they present as non-negotiable
- how others describe them

### 3. Expression DNA

Extract:

- catchphrases and repeated words
- sentence length and rhythm
- punctuation and emoji habits
- directness vs indirectness
- how tone changes with managers, peers, juniors, or group chats
- examples of realistic replies

### 4. Decision and Judgment

Extract:

- priority order during tradeoffs
- what makes them move fast
- what makes them delay
- how they say no
- how they respond to criticism

### 5. Interpersonal Behavior

Extract behavior toward:

- managers
- juniors or direct reports
- peers
- cross-functional partners
- people outside their scope

Include typical scenes and likely replies.

### 6. Boundaries and Triggers

Extract:

- topics they avoid
- requests they reject
- behavior that annoys them
- conflict and repair patterns

## Output Requirements

- Write in English.
- Use short quoted evidence when helpful.
- Preserve uncertainty explicitly.
- Produce concrete behavioral rules that can be used directly in `persona.md`.
