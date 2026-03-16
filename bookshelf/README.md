# BookShelf — [live demo](https://redis-roadmap-seven-inky.vercel.app/)

A personal technical library built from epub files, with API-enriched details,
cover art, and site-visitor vote counts of what books look interesting.

For the motivation and context behind this project, see the [repo README](../README.md).
This document covers the technical implementation.

![BookShelf screenshot](public/demo-1-screenshot-1.png)

## What it does

- Browsable library with cover art, titles, and authors
- Per-book upvote counts, persistent and visible to all visitors
- Tag-based filtering (AI-generated tags coming soon)

## How it's built

**Frontend:** Next.js (App Router) + TypeScript + Tailwind CSS v4, deployed on Vercel.

**Data:** Book metadata and vote counts live in [Upstash Redis](https://upstash.com/),
namespaced by environment so that dev, preview, and prod stay isolated.

**Book pipeline:** A Python script walks a folder of epub files, pulls metadata from each
file's embedded OPF manifest, enriches it via the Google Books API, and extracts cover images
directly from the epub zip. A TypeScript seed script writes the results to Redis. Cover images
are committed to the repo and served as static assets — no external image CDN at runtime.

## Stack

- Next.js 16 / React 19
- TypeScript
- Tailwind CSS v4
- Upstash Redis
- Python (data pipeline, local only)

## Running locally

```env
# .env.local
UPSTASH_REDIS_REST_URL=...
UPSTASH_REDIS_REST_TOKEN=...
BOOKS_DIR="..."            # root folder containing epub bundle subfolders
GOOGLE_BOOKS_API_KEY=...   # for metadata enrichment
```

```bash
npm install
npm run dev
```

The data pipeline (`scripts/extract_books.py`) runs locally and requires `BOOKS_DIR` and
`GOOGLE_BOOKS_API_KEY`. See `CLAUDE.md` for pipeline commands and Redis seeding options.
