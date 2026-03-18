"use client"

import Image from "next/image"
import type { Book } from "@/lib/books"

function BookCover({ coverUrl, title }: { coverUrl?: string; title: string }) {
  if (coverUrl) {
    return (
      <div className="shrink-0 w-16 h-20 min-[375px]:w-24 min-[375px]:h-30 relative rounded overflow-hidden bg-gray-100 dark:bg-gray-800">
        <Image src={coverUrl} alt={`Cover of ${title}`} fill className="object-contain" unoptimized />
      </div>
    )
  }
  return <div className="shrink-0 w-16 h-20 min-[375px]:w-24 min-[375px]:h-30 rounded bg-gray-100 dark:bg-gray-800" />
}

function BookHeader({ title, author, tags, ai_tags }: { title: string; author: string; tags: string[]; ai_tags?: string[] }) {
  return (
    <div className="min-w-0 flex-1">
      <p className="font-semibold leading-snug">{title}</p>
      <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{author}</p>
      <div className="flex flex-wrap gap-1 mt-2">
        {tags.map((tag) => (
          <span key={tag} className="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300">
            {tag}
          </span>
        ))}
        {ai_tags?.map((tag) => (
          <span key={tag} className="text-xs px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-300">
            {tag}
          </span>
        ))}
      </div>
    </div>
  )
}

// Placeholder for expandable book details
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function BookDetails({ book }: { book: Book }) {
  return null
}

function VoteButton({ isbn, votes, onVote }: { isbn: string; votes: number; onVote: (isbn: string) => void }) {
  return (
    <button
      onClick={() => onVote(isbn)}
      className="w-16 min-[375px]:w-24 md:w-auto shrink-0 flex flex-row md:flex-col items-center gap-2 md:gap-0.5 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-800 hover:border-gray-400 dark:hover:border-gray-600 transition-colors text-sm font-medium"
    >
      <span>+1</span>
      <span className="text-gray-400 dark:text-gray-500">{votes}</span>
    </button>
  )
}

type BookTileProps = {
  book: Book
  votes: number
  onVote: (isbn: string) => void
}

export function BookTile({ book, votes, onVote }: BookTileProps) {
  return (
    <li className="flex flex-col md:flex-row md:items-start gap-3 md:gap-4 p-4 rounded-lg border border-gray-200 dark:border-gray-800">
      <div className="flex gap-4 flex-1 min-w-0">
        <BookCover coverUrl={book.coverUrl} title={book.title} />
        <BookHeader title={book.title} author={book.author} tags={book.tags} ai_tags={book.ai_tags} />
        <BookDetails book={book} />
      </div>
      <VoteButton isbn={book.isbn} votes={votes} onVote={onVote} />
    </li>
  )
}
