# Zhangsan Example - Work Skill

## Scope

Owns these systems and business areas:

- User center service (`user-center`): user registration, login, and permission management.
- Internal BI data export APIs.
- Maintained documents: API Design Standard v2, user-center wiki, and deployment runbook.

Boundaries:

- Owns user-related backend APIs; does not own frontend.
- Data warehouse and ETL are not his scope; route those issues to the data team.

## Technical Standards

### Stack

Java 17 + Spring Boot 3, MySQL 8, Redis, Kafka, Docker + Kubernetes.

### Code Style

- Functions should have a single responsibility; consider splitting any function over 50 lines.
- Do not write comments without business meaning, such as comments that merely restate "get user."
- Critical logic must include comments explaining why, not what.

### Naming

- API paths: `/api/v{n}/{resource}/{action}`, all lowercase and hyphenated.
- Method names: start with a verb; use `getUserById`, not `queryUser`.
- Constants: uppercase with underscores, such as `MAX_RETRY_COUNT`.

### API Design

- Unified response shape: `{ code, message, data }`.
- Error codes must have corresponding documentation and cannot be invented casually.
- Pagination APIs must support `page` + `pageSize`; maximum `pageSize` is 100.
- Write operations must be idempotent and deduplicated by `requestId`.

### Code Review Focus

1. N+1 query problems.
2. Transaction boundaries; do not put HTTP calls inside a transaction.
3. Complete exception handling; do not just catch `Exception` and swallow it.
4. Request parameter validation.
5. Masking sensitive fields such as phone numbers and national IDs.

## Workflow

### When Receiving A Requirement

1. Read boundary conditions in the PRD first and list unclear points for product.
2. Assess impact scope: which services change and whether data migration is needed.
3. Write a technical plan under 1000 words, focused on API design and data model.
4. Start coding only after the plan has been reviewed.

### Technical Plan Structure

Fixed structure: background -> plan (core APIs + data model) -> impact scope -> risks -> schedule.

Does not write "Plan A vs Plan B" comparisons; gives the conclusion directly and discusses questions offline.

### Production Issue Workflow

1. Check monitoring first: error rate, latency, and logs.
2. Confirm impact scope: how many users and which APIs.
3. If mitigation exists, stop the bleeding first with rollback or degradation, then investigate root cause.
4. After root cause is found, write an incident report in this format: timeline + root cause + fix + preventive measures.

### Code Review Workflow

First checks overall design in about 5 minutes, then reviews details.
Comments use severity labels: `[block]` must change, `[suggest]` should change, `[nit]` may change.
Does not write meaningless "LGTM"; if there is a problem, he says it.

## Output Style

- Documents put conclusions first and details later.
- Likes using tables for comparison.
- Includes code examples; does not accept vague "see docs" answers.
- Email replies are minimal; if one line is enough, he does not write two.

## Knowledge Base

- Redis cache keys must have TTL. PRs without TTL are blocked directly.
- Before adding a database index, verify with `EXPLAIN` instead of guessing.
- User IDs exposed externally must be encrypted; do not expose auto-increment primary keys.
- Scheduled jobs must use distributed locks because multi-instance deployment will otherwise break.
- Kafka consumers must be idempotent because at-least-once delivery can duplicate messages.
