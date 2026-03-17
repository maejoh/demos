# demos — portfolio repo

## Purpose
A portfolio built around a single app — **BookShelf** — where each new capability
(Redis layer, epub pipeline, Anthropic API, MCP tooling) is a natural extension of
the product rather than a standalone demo. The codebase is written for public
readability: structured, clean, and navigable by anyone who wants to see how a
specific part works.

Test coverage and READMEs are treated as first-class — they should stay current
with the code and be readable by someone encountering the project for the first time.

## App
**BookShelf** (`bookshelf/`) — a Next.js app for managing and browsing a personal book
collection, deployed on Vercel.

Capabilities to date:
- Redis-backed book shelf, namespaced by environment (prod/dev/preview)
- TypeScript seed script with per-environment targeting and wipe support
- Epub processing pipeline (Python, runs locally): OPF extraction → Google Books enrichment → cover image extraction

Planned:
- **AI tagging** — Anthropic API call in the epub pipeline to generate and normalize tags across the library
- **LLM features on the site** — book recommendations, job description matching, natural language queries about the library
- **MCP server** — hand-rolled, composable with the LLM layer
- **Agentic demo** — React frontend + LLM + MCP tool(s)

## Deployment
- Host: Vercel
- Prod: https://redis-roadmap-seven-inky.vercel.app/

## Workflow (gstack skills)

Skills live in `.claude/skills/` (forked from
[garrytan/gstack](https://github.com/garrytan/gstack)).
Claude Code auto-discovers them — no install step needed.

| Phase   | Skill               | When to use                                                           |
|---------|---------------------|-----------------------------------------------------------------------|
| Concept | `/plan-ceo-review`  | Before committing to new work — challenge scope, find the 10x version |
| Plan    | `/plan-eng-review`  | Before building — lock architecture, data flow, edge cases            |
| Review  | `/review`           | Before any push — checks diff against portfolio checklist             |
| Test    | `/qa`               | After building — systematic test pass scoped to git diff              |
| Ship    | `/ship`             | When ready — builds, lints, merges, pushes, opens PR                  |

## Preferences
I usually use Claude in 'edit automatically' mode, but I prefer that edits only
happen when I explicitly ask for them, and not just when Claude thinks there's a
clear answer to my question. If I ask a question, answer the question — don't
modify the codebase yet.
