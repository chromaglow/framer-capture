# Framer — instructions for Claude Code

This folder (`C:\dev\GitHub\framer`) is the repo for **Framer**, a Windows repeat-frame screen capture app.

## Your task
Build the complete MVP described in **`FRAMER_SPEC.md`** in this folder. Read the whole spec before writing code. It is the single source of truth.

## How to work
- **Work autonomously. Do not ask the owner questions.** Every product decision is already in the spec. When something is ambiguous or blocked, choose the simplest option that meets the spec's Acceptance Criteria (§14), log it as one line in `DECISIONS.md`, and continue.
- Follow the milestones in spec §15 in order. Run the tests and make a git commit at the end of each milestone.
- If this folder is not yet a git repo, run `git init` (default branch `main`) first.
- If `gh` is authenticated, create a **private** GitHub repo named `framer` under the authenticated account, add it as `origin`, push, and set up the workflow in spec §12.4. If `gh` is not available or not authenticated, skip the remote and build locally; note it in `DECISIONS.md`.
- You are on Windows: build the exe locally (spec §12.4) and place it at `release\Framer.exe`.
- The owner does not use a terminal. The finished product must run by double-clicking `release\Framer.exe`, with no setup steps.
- No telemetry, no network calls in the app, no auto-update.

## Definition of done
1. All automated tests pass (spec §14.1).
2. `release\Framer.exe --self-test` exits 0 (spec §13).
3. The self-check list in spec §14.2 is completed and results are recorded in `DECISIONS.md`.
4. `README.md` is written for the owner in plain language (spec §16).
5. Final commit made (and tagged `v1.0.0` / pushed if a remote exists).

When done, print a short summary: where the exe is, test results, and any deviations from the spec.
