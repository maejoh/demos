

## Environment variables (`.env.local`)
```
UPSTASH_REDIS_REST_URL=...            # for updating the database from the output files
UPSTASH_REDIS_REST_TOKEN=...          # for updating the database from the output files
BOOKS_DIR="E:\path\to\epub bundles"   # local only — root folder containing bundle subfolders
GOOGLE_BOOKS_API_KEY=...              # for ISBN lookup and metadata enrichment
ANTHROPIC_API_KEY=...                 # for AI tagging
BOOK_BUNDLES=Bundle One,Bundle Two    # comma-separated subfolder names for --all flag
```

## Data pipeline

### 1. Extract
```
npm run extract -- --bundle "Bundle Name"   # extract one subfolder from BOOKS_DIR
npm run extract -- --all                    # extract all bundles listed in BOOK_BUNDLES
npm run extract -- /path/to/folder          # extract from an explicit folder path
```
`scripts/book_pipeline/extract_books.py` walks a folder of epubs, extracts metadata from OPF,
enriches title/author/year/description/cover via the Google Books API, and extracts cover images
from the epub zip.

Outputs:
- `scripts/output/book_list.json` — `{isbn, title, title_raw}[]` — tracks scanned books with ISBNs
- `scripts/output/book_list_manual_isbn.json` — same shape — no-ISBN epubs; fill in ISBNs manually to promote to book_list on next run
- `scripts/output/book_details.json` — `{[isbn]: Book}` — full enriched data, source of truth for seed
- `public/covers/{isbn}.{ext}` — cover images extracted from epubs

Flags:
- `--bundle "Name"` — resolve subfolder from `BOOKS_DIR`
- `--all` — iterate all bundles in `BOOK_BUNDLES`
- `--mode fast` (default) — skip already-enriched books
- `--mode overwrite` — re-enrich all books, preserve existing data
- `--mode clean` — delete output files and run fresh
- `--list-only` — extract epub metadata and update book lists only, skip all API calls

Skip logic: fast mode skips books whose ISBN is already a key in `book_details.json`. No-ISBN epubs go to `book_list_manual_isbn.json`; fill in the isbn field and re-run to enrich.

### 2. Tag
```
npm run tag                    # discover vocabulary + tag untagged books
npm run tag -- --clean         # rebuild vocabulary + retag all books
npm run tag -- --normalize     # skip vocabulary pass, reassign tags from existing vocabulary
npm run tag -- --isbn ISBN     # retag a single book
```
`scripts/book_pipeline/tag_books.py` uses the Anthropic API in two passes:
- **Pass 1** — sends all book titles in one call to discover a canonical tag vocabulary (specific tools/languages + broad topic categories)
- **Pass 2** — sends all books + vocabulary in one call to assign 1-3 tags per book

### 3. Seed
```
npm run seed               # → "development" namespace
npm run seed -- --clean    # wipe namespace first, then seed
npm run seed:preview       # → "preview" namespace
npm run seed:prod          # → "production" namespace
```
`scripts/book_pipeline/seed.ts` reads `book_details.json` and writes to Redis. Re-seeding preserves existing vote counts. `--wipe` deletes all keys in the target namespace before seeding.

## Redis key structure
All keys are prefixed by environment namespace (e.g. `development:`, `production:`):
```
{env}:book:{isbn}     → JSON string of Book
{env}:books:all       → Redis set of all ISBNs
{env}:votes:{isbn}    → integer vote count
```

## Cover images
Extracted from epub files at extraction time and saved to `public/covers/`. The `coverUrl` field stored in Redis is a relative path like `/covers/{isbn}.jpg`. These are served statically by Next.js/Vercel — no external CDN or API needed at runtime.