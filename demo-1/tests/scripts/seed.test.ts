import { describe, it, expect, vi, beforeEach } from "vitest"
import { seedBooks } from "@/scripts/seed"
import type { Book } from "@/lib/books"
import type { Redis } from "@upstash/redis"

// minimal redis mock — only the methods seedBooks actually calls
const makeRedisMock = () => ({
  keys: vi.fn().mockResolvedValue([]),
  del: vi.fn().mockResolvedValue(0),
  set: vi.fn().mockResolvedValue("OK"),
  sadd: vi.fn().mockResolvedValue(1),
  exists: vi.fn().mockResolvedValue(0), // 0 = key doesn't exist yet
})

const makeBook = (overrides: Partial<Omit<Book, "votes">> = {}): Omit<Book, "votes"> => ({
  id: "1",
  title: "Test Book",
  author: "Some Author",
  isbn: "9781234567890",
  year: 2020,
  tags: ["JavaScript"],
  description: "A test book",
  ...overrides,
})

describe("seedBooks", () => {
  let redis: ReturnType<typeof makeRedisMock>

  beforeEach(() => {
    redis = makeRedisMock()
  })

  it("skips books with no ISBN and reports the count", async () => {
    const books = {
      a: makeBook({ isbn: "", title: "No ISBN Book" }),
    }
    const { seeded, skipped } = await seedBooks(redis as unknown as Redis, books, "test", false)

    expect(skipped).toBe(1)
    expect(seeded).toBe(0)
    expect(redis.set).not.toHaveBeenCalled()
  })

  it("writes book data, ISBN index, and vote key for a valid book", async () => {
    const book = makeBook()
    const { seeded } = await seedBooks(redis as unknown as Redis, { a: book }, "test", false)

    expect(seeded).toBe(1)
    expect(redis.set).toHaveBeenCalledWith("test:book:9781234567890", JSON.stringify(book))
    expect(redis.sadd).toHaveBeenCalledWith("test:books:all", "9781234567890")
    expect(redis.set).toHaveBeenCalledWith("test:votes:9781234567890", 0)
  })

  it("preserves existing vote counts on re-seed", async () => {
    const book = makeBook()
    // exists() returning 1 means the votes key already exists
    redis.exists.mockResolvedValue(1)

    await seedBooks(redis as unknown as Redis, { a: book }, "test", false)

    // set should only have been called once — for book data, not votes
    const voteCalls = redis.set.mock.calls.filter(([key]) =>
      (key as string).startsWith("test:votes:")
    )
    expect(voteCalls).toHaveLength(0)
  })

  it("deletes all namespace keys when wipe is true", async () => {
    redis.keys.mockResolvedValue(["test:book:111", "test:votes:111", "test:books:all"])

    await seedBooks(redis as unknown as Redis, {}, "test", true)

    expect(redis.keys).toHaveBeenCalledWith("test:*")
    expect(redis.del).toHaveBeenCalledWith("test:book:111", "test:votes:111", "test:books:all")
  })
})
