# demo-1 — BookShelf

A personal bookshelf built from epub bundles. Users can browse and upvote books.

## Stack
- **Framework**: Next.js (App Router), TypeScript, Tailwind v4
- **Data store**: Upstash Redis (namespaced by environment)
- **Data pipeline**: Python scripts → `book_details.json` → Redis

## Environment variables (`.env.local`)
```
UPSTASH_REDIS_REST_URL=...
UPSTASH_REDIS_REST_TOKEN=...
BOOKS_DIR="E:\path\to\epub bundles"   # local only — root folder containing bundle subfolders
GOOGLE_BOOKS_API_KEY=...              # for metadata enrichment
```

## Data pipeline

### 1. Extract
```
npm run extract:llm        # extract a specific aliased bundle (uses BOOKS_DIR + bundle name)
npm run extract            # extract from a folder path directly
```
`scripts/extract_books.py` walks a folder of epubs, extracts metadata from OPF, enriches title/author/year/description via Google Books API, and extracts cover images directly from the epub zip.

Outputs:
- `scripts/book_list.json` — `{isbn, title, title_raw}[]` — used for tracking scanned books, informs skip logic to avoid re-processing books when --force isn't specified
- `scripts/book_details.json` — `{[isbn]: Book}` — full enriched data, only missing books without ISBNs
- `public/covers/{isbn}.{ext}` — cover images extracted from epubs. Not all are guaranteed to exist.

Flags:
- `--bundle "Name"` — resolve subfolder from `BOOKS_DIR`
- `--overwrite` — replace output files instead of merging
- `--force` — re-process all epubs, even known ones

Skip logic: skips epubs already in `book_list.json` by ISBN (or title if no ISBN), **only if the entry has a non-empty ISBN** (entries with no ISBN are always retried).

### 2. Seed
```
npm run seed               # → "development" namespace
npm run seed -- --wipe     # wipe namespace first, then seed
npm run seed:preview       # → "preview" namespace
npm run seed:prod          # → "production" namespace
```
`scripts/seed.ts` reads `book_details.json` and writes to Redis. Re-seeding preserves existing vote counts. `--wipe` deletes all keys in the target namespace before seeding — use this to fix duplicate/stale entries.

## Redis key structure
All keys are prefixed by environment namespace (e.g. `development:`, `production:`):
```
{env}:book:{isbn}     → JSON string of Book
{env}:books:all       → Redis set of all ISBNs
{env}:votes:{isbn}    → integer vote count
```

## Cover images
Extracted from epub files at extraction time and saved to `public/covers/`. The `coverUrl` field stored in Redis is a relative path like `/covers/{isbn}.jpg`. These are served statically by Next.js/Vercel — no external CDN or API needed at runtime.

## Key folders and files
- `app/` — Next.js app router
  - `components/BookShelf.tsx` — main UI component
- `lib/` — shared utilities
  - `books.ts` — `Book` type definition and Redis fetch helpers
- `scripts/` — data pipeline (not deployed)
  - `extract_books.py` — epub extraction + Google Books enrichment
  - `seed.ts` — Redis seeding script
  - `book_details.json` — source of truth for seed *(not committed)*
  - `book_list.json` — scanned epub index, drives skip logic *(not committed)*
- `public/covers/` — cover images extracted from epubs, served statically
- `next.config.ts` — Next.js config
