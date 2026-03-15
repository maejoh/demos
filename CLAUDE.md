# demos — portfolio repo

## Purpose
A portfolio of deployed demos targeting AI companies. Each demo should be live, linkable, and self-explanatory.

## Deployment
- Host: Vercel
- Each demo lives in its own subfolder (`demo-1/`, `demo-2/`, etc.)
- Milestones are "deployed and linkable", moving from simple but complete React/typesript projects to more advanced demos with MCP and Anthropic API calls.


## Structure
```
demos/
  demo-1/   — BookShelf (Next.js + Redis + epub pipeline)
```

## Workflow (gstack skills)

Skills live in `.claude/skills/gstack/` (forked from [garrytan/gstack](https://github.com/garrytan/gstack)). Claude Code auto-discovers them — no install step needed.

| Phase | Skill | When to use |
|---|---|---|
| Concept | `/plan-ceo-review` | Before committing to a new demo — challenge scope, find the 10-star version |
| Plan | `/plan-eng-review` | Before building — lock architecture, data flow, edge cases |
| Review | `/review` | Before any push — checks diff against portfolio checklist |
| Test | `/qa` | After building — systematic test pass scoped to git diff |
| Ship | `/ship` | When ready — merges main, runs build+lint, reviews, pushes, opens PR |

## Preferences
I usually use Claude in 'edit automatically' mode, but I prefer that edits only happen when I explicitly ask for them, and not just when Claude thinks there's a clear answer to my question and assumes that implementing it is what I want it to do next. If I ask a question, answer the question, don't modify the code base yet.