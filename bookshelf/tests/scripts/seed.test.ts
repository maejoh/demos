import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { join } from "path"
import { tmpdir } from "os"
import { writeFileSync, unlinkSync } from "fs"
import { seedBooks, main } from "@/scripts/book_pipeline/seed"
import type { Book } from "@/lib/books"
import { Redis } from "@upstash/redis"

vi.mock("@upstash/redis", () => ({
  Redis: { fromEnv: vi.fn() },
}))

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

  it("deletes all namespace keys when clean is true", async () => {
    redis.keys.mockResolvedValue(["test:book:111", "test:votes:111", "test:books:all"])

    await seedBooks(redis as unknown as Redis, {}, "test", true)

    expect(redis.keys).toHaveBeenCalledWith("test:*")
    expect(redis.del).toHaveBeenCalledWith("test:book:111", "test:votes:111", "test:books:all")
  })

  it("skips del when clean is true but namespace has no keys", async () => {
    redis.keys.mockResolvedValue([]) // empty namespace

    await seedBooks(redis as unknown as Redis, {}, "test", true)

    expect(redis.keys).toHaveBeenCalledWith("test:*")
    expect(redis.del).not.toHaveBeenCalled()
  })

  it("does not call keys or del when clean is false", async () => {
    await seedBooks(redis as unknown as Redis, {}, "test", false)

    expect(redis.keys).not.toHaveBeenCalled()
    expect(redis.del).not.toHaveBeenCalled()
  })

  it("correctly counts seeded and skipped across multiple books", async () => {
    const books = {
      a: makeBook({ isbn: "9781111111111", title: "Book A" }),
      b: makeBook({ isbn: "", title: "No ISBN" }),
      c: makeBook({ isbn: "9782222222222", title: "Book C" }),
    }

    const { seeded, skipped } = await seedBooks(redis as unknown as Redis, books, "test", false)

    expect(seeded).toBe(2)
    expect(skipped).toBe(1)
  })
})

describe("main", () => {
  const savedArgv = process.argv
  const NO_ENV = join(tmpdir(), "nonexistent-seed-test.env")
  const NO_DETAILS = join(tmpdir(), "nonexistent-seed-details.json")

  beforeEach(() => {
    vi.spyOn(process, "exit").mockImplementation((() => {
      throw new Error("process.exit called")
    }) as any)
    vi.spyOn(console, "log").mockImplementation(() => {})
    vi.spyOn(console, "error").mockImplementation(() => {})
  })

  afterEach(() => {
    process.argv = savedArgv
    vi.restoreAllMocks()
  })

  it("exits when --env value is not one of the allowed environments", async () => {
    process.argv = ["node", "seed.ts", "--env", "staging"]

    await expect(main({ envPath: NO_ENV, detailsPath: NO_DETAILS })).rejects.toThrow("process.exit called")
    expect(process.exit).toHaveBeenCalledWith(1)
  })

  it("exits when book_details.json does not exist", async () => {
    process.argv = ["node", "seed.ts"]

    await expect(main({ envPath: NO_ENV, detailsPath: NO_DETAILS })).rejects.toThrow("process.exit called")
    expect(process.exit).toHaveBeenCalledWith(1)
  })

  it("parses env vars from the env file when it exists", async () => {
    process.argv = ["node", "seed.ts"]
    const envPath = join(tmpdir(), `seed-test-${Date.now()}.env`)
    writeFileSync(envPath, "SEED_TEST_VAR=hello\n# comment\nSEED_OTHER=world\n")

    try {
      await expect(main({ envPath, detailsPath: NO_DETAILS })).rejects.toThrow("process.exit called")
      expect(process.env.SEED_TEST_VAR).toBe("hello")
      expect(process.env.SEED_OTHER).toBe("world")
    } finally {
      unlinkSync(envPath)
      delete process.env.SEED_TEST_VAR
      delete process.env.SEED_OTHER
    }
  })

  it("reads book_details.json and seeds books when all inputs are valid", async () => {
    process.argv = ["node", "seed.ts"]
    const bookData = { a: makeBook() }
    const detailsPath = join(tmpdir(), `seed-test-${Date.now()}.json`)
    writeFileSync(detailsPath, JSON.stringify(bookData))

    const redisMock = makeRedisMock()
    vi.mocked(Redis.fromEnv).mockReturnValue(redisMock as any)

    try {
      await main({ envPath: NO_ENV, detailsPath })
    } finally {
      unlinkSync(detailsPath)
    }

    expect(redisMock.set).toHaveBeenCalledWith(
      "development:book:9781234567890",
      expect.any(String)
    )
  })
})
