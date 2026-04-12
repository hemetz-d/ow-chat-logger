# Iteration Process

Internal working process for backlog iterations.

> **Before anything else pull the latest changes: `git pull --rebase origin master`**
> Do not read the task list, do not select a task, until this has run.
> If conflicts happen, stop and notify about it.

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
git pull --rebase origin master
```

Pick the next task from `TASKS.md`. Priority order by default:

1. **bug** — correctness problems
2. **structural** — interface or safety issues
3. **smell** — cleanup and consistency

Skip tasks with state `deferred` — they are on hold by design. Skip tasks with state `review` or `done` — they are already handled. Only pick from `open` tasks.

**Present the selected task to the human and wait for explicit acceptance before proceeding.** Show the task ID, title, severity, and a one-line summary of the intended fix. Do not update `TASKS.md`, read source files, or run any tests until the human confirms.

If the human rejects the task, pick the next candidate by priority and repeat the proposal step.

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
- Whether any new tasks should be opened as a side-effect of the fix

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

**Regression tests must be run both before and after every change, without exception.**

#### 5a. Capture a baseline (before touching any code)

Run the full regression suite on the unmodified branch and record the results:

```bash
pytest --run-ocr tests/test_regression_screenshots.py
pytest
```

Note which tests pass and which fail. This is the **baseline**. Save or copy the output so you can compare it after the fix.

#### 5b. Run tests after the fix

After the change, run the exact same two commands again:

```bash
pytest --run-ocr tests/test_regression_screenshots.py
pytest
```

#### 5c. Regression rule (hard requirement)

Compare the post-fix results against the baseline:

- **No test that was passing before may now fail.** Any new failure is a regression and blocks the iteration — revert or fix before proceeding.
- Tests that were already failing before the change may remain failing, **provided the failure count did not increase and the failure reason did not change**.
- New tests added as part of the task must pass.

Document both the before and after results (pass/fail counts, any changed tests) when presenting for human review. A fix that introduces any new failure is still `in-progress`, not `review`.

### 6. Human Review (mandatory)

Mark the task state `review` in `TASKS.md` and present to the human:

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
- Update the tracking table at the **top** of `TASKS.md` (the `| ID | Title | ... |` table under `## Completion Tracking`).
- Move the task's detailed entry from its active section to the `## Completed and Deferred` section at the bottom of `TASKS.md`.
- Commit the change with a message that references the task ID (e.g. `fix(T-01): sliding Y-anchor in reconstruct_lines`).
- If working in a git worktree or feature branch, open a pull request to `master` rather than committing directly.

---

## Task State Reference

Update the `State:` field in both the tracking table and the detailed entry at each transition.

| State | Meaning |
|-------|---------|
| `open` | Not started |
| `in-progress` | Actively being worked |
| `review` | Fix complete, awaiting human review and test confirmation |
| `done` | Human-approved, tests pass, completion date recorded |
| `deferred` | On hold — problem acknowledged but not actionable yet; do not pick |

---

## Notes

- Do not skip the human review step for "obvious" fixes. Small changes cause regressions.
- Do not mark `done` before tests pass. A task with a passing diff but failing tests is still `in-progress`.
- If a task turns out to be invalid (problem doesn't exist, was already fixed), close it with state `done`, note the reason, and record the date.
- Independent smell tasks can be batched into a single commit if they are genuinely mechanical and non-overlapping, but each still gets its own review checkpoint.
- If you discover a new problem while working on a task, open a new task entry rather than expanding the current task's scope.
