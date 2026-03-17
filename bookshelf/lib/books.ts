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

export async function fetchBooks(): Promise<Book[]> {
  const isbns = await redis.smembers(key("books:all"))
  if (isbns.length === 0) return []

  const [bookData, voteData] = await Promise.all([
    redis.mget<(Book | null)[]>(...isbns.map(isbn => key(`book:${isbn}`))),
    redis.mget<(number | null)[]>(...isbns.map(isbn => key(`votes:${isbn}`))),
  ])

  return isbns
    .map((_, i) => {
      const book = bookData[i]
      if (!book) return null
      return { ...book, votes: voteData[i] ?? 0 }
    })
    .filter((b): b is Book => b !== null)
    .sort((a, b) => a.title.localeCompare(b.title))
}

// Fallback mock data for local development without Redis
export const mockBooks: Book[] = [
  {
    id: "1",
    title: "You Don't Know JS: Scope & Closures",
    author: "Kyle Simpson",
    isbn: "",
    year: 2014,
    tags: ["JavaScript"],
    description: "",
    votes: 0,
  },
  {
    id: "2",
    title: "Programming TypeScript",
    author: "Boris Cherny",
    isbn: "9781492037651",
    year: 2019,
    tags: ["TypeScript"],
    description: "",
    votes: 0,
  },
  {
    id: "3",
    title: "Learning React",
    author: "Alex Banks & Eve Porcello",
    isbn: "9781492051725",
    year: 2020,
    tags: ["React", "JavaScript"],
    description: "",
    votes: 0,
  },
  {
    id: "4",
    title: "Designing Data-Intensive Applications",
    author: "Martin Kleppmann",
    isbn: "9781449373320",
    year: 2017,
    tags: ["Databases", "Systems Design"],
    description: "",
    votes: 0,
  },
  {
    id: "5",
    title: "The Pragmatic Programmer",
    author: "David Thomas & Andrew Hunt",
    isbn: "9780135957059",
    year: 2019,
    tags: ["Software Engineering"],
    description: "",
    votes: 0,
  },
  {
    id: "6",
    title: "Learning SQL",
    author: "Alan Beaulieu",
    isbn: "9780596520830",
    year: 2009,
    tags: ["SQL", "Databases"],
    description: "",
    votes: 0,
  },
  {
    id: "7",
    title: "A Philosophy of Software Design",
    author: "John Ousterhout",
    isbn: "9781732102201",
    year: 2018,
    tags: ["Software Engineering", "Software Architecture"],
    description: "",
    votes: 0,
  },
  {
    id: "8",
    title: "Discrete Mathematics and Its Applications",
    author: "Kenneth Rosen",
    isbn: "9781259676512",
    year: 2018,
    tags: ["Computer Science", "Mathematics"],
    description: "",
    votes: 0,
  },
]
