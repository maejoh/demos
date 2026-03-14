/**
 * Seed Redis with book data from scripts/book_details.json.
 *
 * Usage:
 *   npm run seed                  # seeds into "development" namespace
 *   npm run seed -- --env preview
 *   npm run seed -- --env production
 *
 * Books are written as JSON strings keyed by ISBN.
 * All ISBNs are tracked in a set for easy listing.
 * Votes are initialised to 0 only if they don't already exist,
 * so re-seeding book data won't reset vote counts.
 */

import { readFileSync, existsSync } from "fs"
import { resolve } from "path"
import { Redis } from "@upstash/redis"
import type { Book } from "../lib/books"

// Load .env.local when running locally (Vercel sets env vars automatically)
const envPath = resolve(process.cwd(), ".env.local")
if (existsSync(envPath)) {
  for (const rawLine of readFileSync(envPath, "utf-8").split("\n")) {
    const line = rawLine.trim()
    const match = line.match(/^([^#\s][^=]*)=(.*)$/)
    if (match) {
      process.env[match[1].trim()] = match[2].trim().replace(/^["']|["']$/g, "")
    }
  }
}

const args = process.argv.slice(2)
const envFlagIndex = args.indexOf("--env")
const env = envFlagIndex !== -1 ? args[envFlagIndex + 1] : "development"

if (!["development", "preview", "production"].includes(env)) {
  console.error(`Invalid --env value: "${env}". Must be development, preview, or production.`)
  process.exit(1)
}

const key = (k: string) => `${env}:${k}`

const detailsPath = resolve(__dirname, "book_details.json")
if (!existsSync(detailsPath)) {
  console.error("book_details.json not found. Run extract_books.py first.")
  process.exit(1)
}

const bookDetails: Record<string, Omit<Book, "votes">> = JSON.parse(
  readFileSync(detailsPath, "utf-8")
)

async function main() {
  const books = Object.values(bookDetails)
  console.log(`Seeding ${books.length} books into Redis namespace "${env}"...\n`)

  const redis = Redis.fromEnv()
  let seeded = 0
  let skipped = 0

  for (const book of books) {
    if (!book.isbn) {
      console.log(`  [skip] "${book.title}" — no ISBN`)
      skipped++
      continue
    }

    // Write book data
    await redis.set(key(`book:${book.isbn}`), JSON.stringify(book))

    // Track ISBN in the index set
    await redis.sadd(key("books:all"), book.isbn)

    // Initialise votes only if not already set (preserves existing vote counts)
    const hasVotes = await redis.exists(key(`votes:${book.isbn}`))
    if (!hasVotes) {
      await redis.set(key(`votes:${book.isbn}`), 0)
    }

    console.log(`  ✓ ${book.title} (${book.isbn})`)
    seeded++
  }

  console.log(`\nDone. ${seeded} seeded, ${skipped} skipped (no ISBN).`)
  console.log(`Keys are prefixed with "${env}:".`)
}

main()
