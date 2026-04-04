# Agent Workflow Guidelines

You are an autonomous agent working on the Penny project. Follow these guidelines for all tasks.

## Before You Start

1. **Read the issue(s)** assigned to you via `gh issue view <id>`
2. **Read agents/CONTEXT.md** to understand the architecture and current state
3. **Review relevant ADRs** in `ADR/` for design decisions that apply to your work
4. **Explore the codebase** to understand existing patterns before writing code

## Implementation

### Code Quality

- Follow existing code patterns and style in the codebase
- Keep changes focused on the issue scope - avoid scope creep
- Prefer editing existing files over creating new ones
- Use the established module structure (see agents/CONTEXT.md)

### Test Coverage

- **Add tests for all new functionality**
- Place tests in `tests/` following existing naming conventions (`test_*.py`)
- Run `make test` before committing to verify all tests pass
- If modifying existing behavior, update affected tests

### Adherence to ADRs

The `ADR/` directory contains architectural decisions. Key ones to follow:

- **ADR-010**: Vault is source of truth, SQLite is derived projection
- **ADR-008**: Classification uses Python rules with file-order precedence
- **ADR-009**: Transfer grouping uses Union-Find algorithm
- **ADR-011**: Flat module structure (accounts.py, transactions.py)

If your implementation requires deviating from an ADR, document why in your PR.

## Commits

- Write clear, descriptive commit messages
- Reference the issue number: `Fix #123` or `Addresses #123`
- Keep commits atomic - one logical change per commit

## Pull Request

When your implementation is complete:

### PR Title
```
<type>: <short description> (#<issue-numbers>)
```
Types: `feat`, `fix`, `refactor`, `test`, `docs`

Example: `feat: Auto-run classification rules during CSV import (#8)`

### PR Body Structure

```markdown
## Summary

Brief description of what this PR does.

Addresses #<issue-number>

## Implementation Notes

Document key decisions and discoveries:

- **Discovery**: <something you learned about the codebase>
- **Decision**: <a choice you made and why>
- **Deviation**: <if you deviated from the issue description, explain why>

## Changes

- List of significant changes made
- New files added (if any)
- Modified behaviors

## Test Plan

- [ ] Added tests for <new functionality>
- [ ] Existing tests pass (`make test`)
- [ ] Manual verification steps (if applicable)
```

### Creating the PR

```bash
gh pr create --title "<title>" --body "<body>"
```

## Example PR

```markdown
## Summary

Implements automatic classification rule execution after CSV import.

Addresses #8

## Implementation Notes

- **Discovery**: The `apply_rules()` function in `classify/engine.py` already supports
  being called incrementally - it only processes unclassified transactions.
- **Decision**: Chose to call rules after `store_transactions()` rather than integrating
  into the transaction storage loop, to keep concerns separated.
- **Deviation**: Issue mentioned "both UI and CLI import" but they already share the same
  code path through `vault/ingest.py`, so only one change was needed.

## Changes

- Modified `vault/apply.py`: Call `apply_rules()` after successful ingest
- Added `tests/test_ingest_with_rules.py`: Verify rules run on import

## Test Plan

- [x] Added test for rules execution during import
- [x] Existing tests pass
- [x] Manually tested with sample CSV
```

## Troubleshooting

- If tests fail, fix them before creating the PR
- If you're blocked, document what's blocking you in the PR description
- If the issue scope is unclear, implement the minimal reasonable interpretation
