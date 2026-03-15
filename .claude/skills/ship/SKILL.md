---
name: ship
version: 1.0.0
description: |
  Ship workflow for demos: merge main, run build + lint, pre-landing review,
  commit, push, create PR. Adapted from garrytan/gstack /ship for
  Vercel-deployed Next.js demos (npm workspaces, no Rails, no CHANGELOG/VERSION).
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
---
<!-- Forked from garrytan/gstack ship v1.0.0 — stripped for npm/Vercel/Next.js demos.
     Removed: Rails test suite, eval suites, Greptile, VERSION bumping, CHANGELOG, TODOS.md automation, bisectable commit splitting. -->

# Ship: Automated Ship Workflow

You are running the `/ship` workflow. This is a **non-interactive, fully automated** workflow. Do NOT ask for confirmation at any step. Run straight through and output the PR URL at the end.

**Only stop for:**
- On `main` branch (abort)
- Merge conflicts that can't be auto-resolved (stop, show conflicts)
- Build or lint failures (stop, show failures)
- Pre-landing review finds CRITICAL issues and user chooses to fix (not acknowledge or skip)

**Never stop for:**
- Uncommitted changes (always include them)
- Commit message approval (auto-commit)

---

## Step 1: Pre-flight

1. Check the current branch. If on `main`, **abort**: "You're on main. Ship from a feature branch."

2. Run `git status` (never use `-uall`). Uncommitted changes are always included — no need to ask.

3. Run `git diff main...HEAD --stat` and `git log main..HEAD --oneline` to understand what's being shipped.

4. **Identify the affected demo subfolder(s):** look at changed files and determine which `demo-*/` subfolder(s) are involved. This tells you where to run build and lint. If changes are only at the repo root (CLAUDE.md, README, `.claude/`), skip Steps 3 and 3.5's build check and go straight to the pre-landing review.

---

## Step 2: Merge origin/main

Fetch and merge `origin/main` so build and review run against the merged state:

```bash
git fetch origin main && git merge origin/main --no-edit
```

**If merge conflicts:** Try to auto-resolve simple ones (whitespace, ordering). If complex or ambiguous, **STOP** and show them.

**If already up to date:** Continue silently.

---

## Step 3: Build and lint

For each affected demo subfolder identified in Step 1:

```bash
cd <demo-dir>
npm run build 2>&1 | tee /tmp/ship_build.txt
npm run lint 2>&1 | tee /tmp/ship_lint.txt
cd -
```

Read both output files and check pass/fail.

**If build or lint fails:** Show the failures and **STOP**. Do not proceed.

**If all pass:** Note the results briefly and continue.

---

## Step 3.5: Pre-Landing Review

Review the diff for structural issues that tests don't catch.

1. Read `.claude/skills/gstack/review/checklist.md`. If the file cannot be read, **STOP** and report the error.

2. Run `git diff origin/main` to get the full diff (committed + uncommitted).

3. Apply the checklist in two passes:
   - **Pass 1 (CRITICAL):** Items marked Critical in the checklist
   - **Pass 2 (INFORMATIONAL):** Remaining checklist items

4. **Output ALL findings** — both critical and informational.

5. Output a summary header: `Pre-Landing Review: N issues (X critical, Y informational)`

6. **If CRITICAL issues found:** For EACH critical issue, use a separate AskUserQuestion with:
   - The problem (file:line + description)
   - Your recommended fix
   - Options: A) Fix it now (recommended), B) Acknowledge and ship anyway, C) False positive — skip

   If user chooses A (fix): apply the fixes, commit only the fixed files (`git add <fixed-files> && git commit -m "fix: apply pre-landing review fixes"`), then **STOP** and tell the user to run `/ship` again to re-test with the fixes applied.

   If user chose only B/C: continue with Step 4.

7. **If only informational issues:** Output and continue. Include in PR body.

8. **If no issues:** Output `Pre-Landing Review: No issues found.` and continue.

Save the review output — it goes into the PR body in Step 5.

---

## Step 4: Commit

Stage all changes and create a commit:

```bash
git add -A
git commit -m "$(cat <<'EOF'
<type>: <summary of changes>

<brief description of what this ships>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

Infer the commit message from the diff and commit history. Use conventional commits format: `feat` for new features, `fix` for bug fixes, `chore` for tooling/config, `refactor` for restructuring, `docs` for documentation.

If there are already commits on the branch (from previous `/ship` attempts or manual commits), do not re-commit already-committed work. Only commit staged/unstaged changes.

---

## Step 5: Push

```bash
git push -u origin <branch-name>
```

---

## Step 6: Create PR

```bash
gh pr create --title "<type>: <summary>" --body "$(cat <<'EOF'
## Summary
<bullet points describing what this ships>

## Pre-Landing Review
<findings from Step 3.5, or "No issues found.">

## Test plan
- [x] Build passes in affected demo(s)
- [x] Lint passes in affected demo(s)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**Output the PR URL** — this should be the final output the user sees.

---

## Important Rules

- **Never skip build/lint** for demo subfolder changes. If they fail, stop.
- **Never skip the pre-landing review.** If checklist.md is unreadable, stop.
- **Never force push.**
- **Never ask for confirmation** except for CRITICAL review findings (one AskUserQuestion per critical issue).
- **The goal is: user says `/ship`, next thing they see is the review + PR URL.**
