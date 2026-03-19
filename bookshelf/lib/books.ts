import { redis, key } from "./redis"

export type Book = {
  id: string
  title: string
  author: string
  isbn: string
  year: number | null
  tags: string[]
  ai_tags?: string[]
  description: string
  coverUrl?: string
  humbleBundle?: string
  votes: number
}

export type FetchBooksResult = { books: Book[]; fetchError: string | null }

export async function fetchBooks(): Promise<FetchBooksResult> {
  try {
    const isbns = await redis.smembers(key("books:all"))
    if (isbns.length === 0) return { books: [], fetchError: null }

    const [bookData, voteData] = await Promise.all([
      redis.mget<(Book | null)[]>(...isbns.map(isbn => key(`book:${isbn}`))),
      redis.mget<(number | null)[]>(...isbns.map(isbn => key(`votes:${isbn}`))),
    ])

    const books = isbns
      .map((_, i) => {
        const book = bookData[i]
        if (!book) return null
        return { ...book, votes: voteData[i] ?? 0 }
      })
      .filter((b): b is Book => b !== null)
      .sort((a, b) => a.title.localeCompare(b.title))

    return { books, fetchError: null }
  } catch (err) {
    console.error("[fetchBooks] Redis error:", err)
    return { books: [], fetchError: "Failed to load books." }
  }
}
