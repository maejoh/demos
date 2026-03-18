"use client"

import type { Book } from "@/lib/books"
import { BookTile } from "./BookTile"

type BookListProps = {
  books: Book[]
  votes: Record<string, number>
  onVote: (isbn: string) => void
}

export function BookList({ books, votes, onVote }: BookListProps) {
  return (
    <ul className="space-y-4">
      {books.map((book) => (
        <BookTile key={book.id} book={book} votes={votes[book.isbn]} onVote={onVote} />
      ))}
    </ul>
  )
}
