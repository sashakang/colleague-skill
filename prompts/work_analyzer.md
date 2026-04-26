# Work Skill Analysis Prompt

## Task

You will receive source material for **{name}**: documents, messages, emails, notes, and other evidence.

Extract work capabilities and working methods for building the Work Skill.

Principles:

- Extract only work-relevant content.
- Ignore casual chat unless it reveals workflow, decision style, or collaboration behavior.
- Do not invent details. If evidence is missing, write `insufficient source material`.
- Preserve direct evidence with short quoted snippets when useful.

## Universal Extraction Dimensions

### 1. Scope

Identify:

- systems, modules, business lines, products, or domains they own
- documents they maintain, such as API docs, wikis, runbooks, or specs
- responsibility boundaries
- project codenames and domain terms they use repeatedly

Output format:

```text
Owned areas: ...
Core systems: ...
Maintained docs: ...
Boundaries: ...
```

### 2. Workflow

Extract:

- steps they take after receiving a task
- design-doc or proposal structure
- progress-management and deadline habits
- incident or urgent-issue handling

Output format:

```text
Task intake: ...
Design docs: ...
Exception handling: ...
```

### 3. Output Preferences

Extract:

- tables, lists, flowcharts, prose, or code examples
- conclusion-first or narrative style
- level of detail
- reply and email style

Output format:

```text
Document style: ...
Detail level: concise | moderate | detailed
```

### 4. Experience Knowledge Base

List explicit lessons, technical opinions, pitfalls, and repeated judgments:

```text
- "short evidence quote or precise summary"
- "short evidence quote or precise summary"
```

## Role-Specific Focus

### Backend or Server Engineer

- stack, frameworks, middleware
- naming conventions for APIs, variables, and functions
- response format, error codes, pagination, idempotency
- database preferences, ORM vs raw SQL, transaction boundaries
- exception handling
- code-review concerns such as N+1 queries, transactions, concurrency, and validation
- deployment, monitoring, rollback, and incident response

### Frontend Engineer

- framework, state management, styling approach
- component boundaries
- performance concerns such as first paint, lazy loading, and bundle size
- API calling and error handling
- linting, formatting, testing, accessibility, responsiveness, and browser compatibility

### ML or Algorithm Engineer

- problem framing and experiment design
- baseline and ablation habits
- offline and online metric preferences
- model families or methods they use
- training framework and deployment process
- data processing standards
- experiment report format and cited methods

### Product Manager or Technical PM

- PRD structure and detail level
- user-story and scope-boundary habits
- alignment process with engineering
- prioritization framework
- data-driven vs intuition-driven decisions
- conflict handling
- artifacts such as PRDs, MRDs, prototypes, competitor analysis, and instrumentation plans

### Designer

- design system and component library
- annotation and handoff standards
- pixel-level expectations
- design-review and acceptance workflow
- handling implementation constraints

### Data Analyst

- funnel, cohort, A/B, or other analysis frameworks
- SQL style and documentation level
- visualization choices
- conclusion-to-data ratio
- metric-definition and data-quality handling

## Output Requirements

- Write in English.
- Use `insufficient source material; add relevant docs` for missing dimensions.
- Mark evidence-based conclusions with short quotes when available.
- Produce content that can be used directly to generate `work.md`.
- Avoid vague phrases such as `maybe`, `seems`, or `tends to` unless the evidence is explicitly weak.
