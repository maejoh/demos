# BookShelf — [live demo](https://redis-roadmap-seven-inky.vercel.app/)

A personal technical reading list, built from a collection of epub files. Browse books by category, see cover art and descriptions, and upvote anything worth recommending.

![BookShelf screenshot](public/demo-1-screenshot-1.png)

## What it does

- Displays a browsable list of books with covers, titles, authors, and descriptions
- Books are grouped by subject (AI, web dev, computer science, math, etc.)
- Anyone can upvote a book — votes persist in Redis and survive page refreshes

## How it's built

**Frontend:** Next.js (App Router) + TypeScript + Tailwind CSS, deployed on Vercel.

**Data:** Book metadata and vote counts are stored in [Upstash Redis](https://upstash.com/). The database is namespaced by environment so development, preview, and production stay separate.

**Book pipeline:** A Python script walks a folder of epub files, pulls metadata (title, author, description, year) from each file's embedded OPF manifest, enriches it via the Google Books API, and extracts the cover image directly from the epub zip. The results get seeded into Redis via a TypeScript seed script. Cover images are committed to the repo and served as static assets — no external image CDN needed at runtime.

## Stack

- Next.js 16 / React 19
- TypeScript
- Tailwind CSS v4
- Upstash Redis
- Python (data pipeline, not deployed)
