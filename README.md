# demos

A collection of live demos built while getting back up to speed after a year away from the industry. Each one is deployed, linkable, and built around something real.

## Projects

### [BookShelf](./demo-1/) — [live demo](https://redis-roadmap-seven-inky.vercel.app/)

A browsable, upvotable reading list built from a personal epub collection.

![BookShelf screenshot](./demo-1/public/demo-1-screenshot-1.png)

---

More coming. Working toward: Anthropic API integration, a hand-rolled MCP server, and a small agentic demo.

---

## Development workflow

This repo uses a forked subset of [garrytan/gstack](https://github.com/garrytan/gstack) skills for Claude Code, committed to `.claude/skills/gstack/`. They're auto-discovered by Claude Code — no install step needed.

| Skill | Source | Customized? |
|---|---|---|
| `/plan-ceo-review` | gstack v1.0.0 | Adapted for TypeScript/Next.js (removed Rails-specific sections) |
| `/plan-eng-review` | gstack v1.0.0 | Adapted for TypeScript/Next.js (removed Rails-specific sections) |
| `/review` | gstack v1.0.0 | Greptile integration removed; checklist path updated |
| `/qa` | gstack v1.0.0 | Template file references removed (files not included) |
| `/ship` | gstack v1.0.0 | **Heavily customized** — Rails tests, evals, Greptile, VERSION/CHANGELOG/TODOS automation all removed; replaced with `npm run build` + `npm run lint` per demo subfolder |
| `review/checklist.md` | — | **Written from scratch** — portfolio-specific criteria (secrets, build integrity, live+linkable+self-explanatory) |
