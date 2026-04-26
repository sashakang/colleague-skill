# Basic Profile Intake Script

## Opening

```text
I can help create this person's Skill. Please answer three questions; every field is optional.
```

## Question Sequence

### Q1: Alias or Code Name

```text
What should we call this person? A nickname, alias, or code name is fine.

Example: qing-yun
```

- Accept any string.
- Normalize generated slugs with hyphens.
- For names that can be romanized, use romanized lowercase words joined by hyphens.
- For English names, lowercase and join words with hyphens.

### Q2: Basic Profile

Ask for company, level, role, and gender in one sentence:

```text
Describe their basic profile in one sentence: company, level, role, gender, or anything you know. You can skip this.

Example: ByteDance L2-1 backend engineer, male
```

Extract these fields when present:

- company
- level
- role
- gender

Reference level table:

| Company | Level format | Engineer | Senior | Expert | Staff/Principal |
|---------|--------------|----------|--------|--------|-----------------|
| ByteDance | X-Y | 2-1, 2-2 | 3-1, 3-2 | 3-3 | 3-3+ |
| Alibaba | P-level | P5, P6 | P7 | P8 | P9+ |
| Tencent | T-level | T1-1 to T2-2 | T3-1, T3-2 | T4 | T4+ |
| Baidu | T-level | T5, T6 | T7 | T8 | T9+ |
| Meituan | P-level | P4, P5 | P6 | P7 | P8+ |
| Huawei | Numeric | 13-15 | 16-17 | 18-19 | 20-21 |

### Q3: Personality Profile

Ask for MBTI, zodiac sign, personality tags, company-culture traits, and subjective impression in one sentence:

```text
Describe their personality in one sentence: MBTI, zodiac sign, personality traits, company-culture style, or your impression. You can skip this.

Example: INTJ, Capricorn, data-driven, strict in code review, rarely explains twice
```

Extract these fields when present:

- MBTI: one of the 16 standard types
- zodiac sign: if provided
- personality tags: match the tag library or preserve custom descriptions
- culture tags: match the culture tag library
- impression: free text that does not fit the structured fields

Personality tag library:

- Work attitude: responsible, good-enough, accountability avoidant, perfectionist, procrastinator
- Communication: direct, indirect, quiet, talkative, voice-message-heavy, read-only, fast responder
- Decision style: decisive, oscillating, manager-dependent, forceful, data-driven, intuition-driven
- Emotional style: steady, sensitive, excitable, distant, outwardly polite, passive-aggressive
- Tactics: political, upward-management-heavy, over-explaining, pressure-building

Culture tag library:

- ByteDance-style: direct, context-heavy, impact-focused, alignment-heavy
- Alibaba-style: value-language-heavy, ecosystem framing, enablement language
- Tencent-style: user-oriented, data-informed, conservative, careful
- Huawei-style: execution-focused, process-heavy, presentation-heavy
- Baidu-style: technical faith, hierarchy-aware, internally competitive
- Meituan-style: detail-oriented, execution-heavy, local-services thinking
- First-principles: asks for fundamentals, avoids analogy, simplifies aggressively
- OKR-focused: asks for objectives first and reviews key results closely
- Big-company process: strong SOPs, low autonomy, risk-avoidant
- Startup-style: resource-constrained, full-stack, outcome-oriented, tolerant of ambiguity

## Confirmation Summary

Show the collected fields:

```text
Profile summary:

  Person: {alias}
  Work: {company} {level} {role}
  Gender: {gender}
  Personality: {MBTI} {zodiac}
  Tags: {personality_tags}
  Culture: {culture_tags}
  Impression: {impression}

Does this look right? Reply confirm, or say modify {field}.
```

After confirmation, move to source-material import.
