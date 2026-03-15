import { describe, it, expect, vi, beforeEach } from "vitest"
import type { Book } from "@/lib/books"
import { fetchBooks } from "@/lib/books"
import { redis } from "@/lib/redis"

// replace the real Redis client with a fake — no credentials needed in tests
vi.mock("@/lib/redis", () => ({
  redis: {
    smembers: vi.fn(),
    mget: vi.fn(),
  },
  // override key() to avoid environment-prefix sensitivity
  key: (k: string) => `test:${k}`,
}))

// reusable book fixture — tests only specify fields relevant to their case
const makeBook = (overrides: Partial<Book> = {}): Book => ({
  id: "1",
  title: "Alpha",
  author: "Some Author",
  isbn: "9781234567890",
  year: 2020,
  tags: ["JavaScript"],
  description: "A test book",
  votes: 0,
  ...overrides,
})

describe("fetchBooks", () => {
  beforeEach(() => {
    // prevent mock state from one test leaking into the next
    vi.clearAllMocks()
  })

  it("returns [] when there are no ISBNs in Redis", async () => {
    vi.mocked(redis.smembers).mockResolvedValue([])
    expect(await fetchBooks()).toEqual([])
  })

  it("merges book data with vote counts from Redis", async () => {
    const book = makeBook()
    vi.mocked(redis.smembers).mockResolvedValue([book.isbn])
    // mget is called twice (book data, then votes) — Once queues per-call return values
    vi.mocked(redis.mget)
      .mockResolvedValueOnce([book])
      .mockResolvedValueOnce([7])

    const [result] = await fetchBooks()
    expect(result.votes).toBe(7)
  })

  it("defaults votes to 0 when vote data is null", async () => {
    const book = makeBook()
    vi.mocked(redis.smembers).mockResolvedValue([book.isbn])
    // null = key exists in the ISBN set but has no vote entry in Redis
    vi.mocked(redis.mget)
      .mockResolvedValueOnce([book])
      .mockResolvedValueOnce([null])

    const [result] = await fetchBooks()
    expect(result.votes).toBe(0)
  })

  it("filters out null book entries from mget", async () => {
    const book = makeBook({ id: "2", title: "Beta", isbn: "9780000000001" })
    vi.mocked(redis.smembers).mockResolvedValue(["9781234567890", book.isbn])
    // null = stale ISBN in the set with no corresponding book object
    vi.mocked(redis.mget)
      .mockResolvedValueOnce([null, book])
      .mockResolvedValueOnce([3, 5])

    const result = await fetchBooks()
    expect(result).toHaveLength(1)
    expect(result[0].isbn).toBe(book.isbn)
  })

  it("sorts results alphabetically by title", async () => {
    // ISBNs are out of alpha order to confirm sort isn't an insertion-order coincidence
    const books = [
      makeBook({ id: "1", title: "Zebra", isbn: "1111111111111" }),
      makeBook({ id: "2", title: "Apple", isbn: "2222222222222" }),
      makeBook({ id: "3", title: "Mango", isbn: "3333333333333" }),
    ]
    vi.mocked(redis.smembers).mockResolvedValue(books.map((b) => b.isbn))
    vi.mocked(redis.mget)
      .mockResolvedValueOnce(books)
      .mockResolvedValueOnce([0, 0, 0])

    const result = await fetchBooks()
    expect(result.map((b) => b.title)).toEqual(["Apple", "Mango", "Zebra"])
  })
})
