# Iteration Process

This document defines how each task in `TASKS.md` is approached, reviewed, and closed. The goal is to keep changes small, verifiable, and human-confirmed before moving on.

---

## Principles

- One task per iteration. Do not bundle unrelated changes.
- Every iteration ends with a human review and a test run before the task is marked `done`.
- The task state in `TASKS.md` is the source of truth. Update it at each stage transition.
- If a fix reveals a new problem, open a new task rather than expanding scope mid-iteration.

---

## Iteration Stages

```
open  -->  in-progress  -->  review  -->  done
                                |
                           (rejected)
                                |
                           in-progress  (revised)
```

### 1. Select

Pull the latest changes from the remote before selecting a task:

```bash
git pull
```

Pick the next task from `TASKS.md`. Priority order by default:

1. **bug** — correctness problems
2. **structural** — interface or safety issues
3. **smell** — cleanup and consistency

Update the task state to `in-progress` before making any changes.

### 2. Understand

Before writing any code:

- Read the flagged file(s) in full.
- Read the associated tests.
- Confirm the problem is reproducible or demonstrable (add a failing test first when possible).
- Note any knock-on effects on other modules.

If the scope turns out to be larger than the task description implies, surface this to the human before proceeding.

### 3. Describe

Before writing any code, produce a short plain-language description of exactly what will be changed:

- Which file(s) and line(s) will be touched
- What the change is (e.g. "remove `__setitem__`" or "wrap mutation in `RLock`")
- What the expected outcome is (what breaks before, what passes after)
- Any alternatives considered and why they were ruled out

Present this to the human and wait for a go-ahead before proceeding to the fix. This step is not optional for structural or larger bug changes. It can be omitted only for smell tasks with a trivially obvious mechanical fix (e.g. delete a comment block).

### 4. Fix

Make the minimal change that addresses the task. Do not refactor surrounding code, rename unrelated things, or fix adjacent smells unless they are explicitly part of the task.

Checklist:
- [ ] Change is limited to what the task describes
- [ ] No new dead code introduced
- [ ] No new commented-out code introduced
- [ ] Existing tests still pass (run before opening for review)
- [ ] New or updated test(s) cover the fix

### 5. Test Execution (mandatory)

Run the full test suite before marking as `review`:

```bash
pytest
```

For changes touching OCR, image processing, or the pipeline:

```bash
pytest --run-ocr tests/test_regression_screenshots.py
```

Document the test result in the task or in the PR. A failing test suite blocks the iteration — fix before escalating to review.

### 6. Human Review (mandatory)

Mark the task state `review` and present to the human:

- What was changed and why (file + line reference)
- What test(s) were added or changed
- Test run result (pass/fail counts)
- Any edge cases or trade-offs noted during the fix

The human inspects the diff, asks questions, and either:
- **Approves** → task moves to `done`, completion date recorded in `TASKS.md`
- **Requests changes** → task stays/returns to `in-progress`, feedback noted, revision cycle repeats from step 4

### 7. Close

After human approval:

- Update task state to `done` and record the completion date in `TASKS.md` (format: `YYYY-MM-DD`).
- Update the tracking table at the bottom of `TASKS.md`.
- Commit the change with a message that references the task ID (e.g. `fix(T-01): sliding Y-anchor in reconstruct_lines`).

---

## Task State Reference

Update the `State:` field in `TASKS.md` at each transition.

| State | Meaning |
|-------|---------|
| `open` | Not started |
| `in-progress` | Actively being worked |
| `review` | Fix complete, awaiting human review and test confirmation |
| `done` | Human-approved, tests pass, completion date recorded |

---

## Notes

- Do not skip the human review step for "obvious" fixes. Small changes cause regressions.
- Do not mark `done` before tests pass. A task with a passing diff but failing tests is still `in-progress`.
- If a task turns out to be invalid (problem doesn't exist, was already fixed), close it with state `done`, note the reason, and record the date.
- Smells (T-10, T-11) can be batched into a single commit if they are genuinely independent, but each still gets its own review checkpoint.
