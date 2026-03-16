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
import { fileURLToPath } from "url"
import { Redis } from "@upstash/redis"
import type { Book } from "../lib/books"

export async function seedBooks(
  redis: Redis,
  bookDetails: Record<string, Omit<Book, "votes">>,
  env: string,
  wipe: boolean
): Promise<{ seeded: number; skipped: number }> {
  const key = (k: string) => `${env}:${k}`
  const books = Object.values(bookDetails)

  if (wipe) {
    console.log(`Wiping all keys in namespace "${env}"...`)
    const keys = await redis.keys(`${env}:*`)
    if (keys.length > 0) {
      await redis.del(...keys)
      console.log(`  Deleted ${keys.length} key(s).\n`)
    } else {
      console.log(`  Nothing to delete.\n`)
    }
  }

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

  return { seeded, skipped }
}

async function main() {
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
  const wipe = args.includes("--wipe")

  if (!["development", "preview", "production"].includes(env)) {
    console.error(`Invalid --env value: "${env}". Must be development, preview, or production.`)
    process.exit(1)
  }

  const detailsPath = resolve(__dirname, "book_details.json")
  if (!existsSync(detailsPath)) {
    console.error("book_details.json not found. Run extract_books.py first.")
    process.exit(1)
  }

  const bookDetails: Record<string, Omit<Book, "votes">> = JSON.parse(
    readFileSync(detailsPath, "utf-8")
  )

  const books = Object.values(bookDetails)
  console.log(`Seeding ${books.length} books into Redis namespace "${env}"...\n`)

  const redis = Redis.fromEnv()
  const { seeded, skipped } = await seedBooks(redis, bookDetails, env, wipe)

  console.log(`\nDone. ${seeded} seeded, ${skipped} skipped (no ISBN).`)
  console.log(`Keys are prefixed with "${env}:".`)
}

// only run when executed directly, not when imported by tests
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main()
}
