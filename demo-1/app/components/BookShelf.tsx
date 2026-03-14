"use client"

import { useState } from "react"
import Image from "next/image"
import type { Book } from "@/lib/books"

export default function BookShelf({ books }: { books: Book[] }) {
  const [activeTag, setActiveTag] = useState<string | null>(null)
  const [votes, setVotes] = useState<Record<string, number>>(
    Object.fromEntries(books.map((b) => [b.id, b.votes]))
  )

  const allTags = Array.from(new Set(books.flatMap((b) => b.tags))).sort()
  const visible = activeTag ? books.filter((b) => b.tags.includes(activeTag)) : books

  function handleVote(id: string) {
    // TODO: replace with server action that persists to Redis
    setVotes((prev) => ({ ...prev, [id]: prev[id] + 1 }))
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-16">
      <header className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight mb-2">My Technical Library</h1>
        <p className="text-gray-500 dark:text-gray-400">
          Books I own, am reading, or have read. +1 anything relevant to you.
        </p>
      </header>

      <div className="flex flex-wrap gap-2 mb-8">
        <TagButton active={activeTag === null} onClick={() => setActiveTag(null)}>
          All
        </TagButton>
        {allTags.map((tag) => (
          <TagButton
            key={tag}
            active={activeTag === tag}
            onClick={() => setActiveTag(activeTag === tag ? null : tag)}
          >
            {tag}
          </TagButton>
        ))}
      </div>

      <ul className="space-y-4">
        {visible.map((book) => (
          <li
            key={book.id}
            className="flex items-start justify-between gap-4 p-4 rounded-lg border border-gray-200 dark:border-gray-800"
          >
            {book.coverUrl ? (
              <div className="shrink-0 w-12 h-16 relative rounded overflow-hidden bg-gray-100 dark:bg-gray-800">
                <Image
                  src={book.coverUrl}
                  alt={`Cover of ${book.title}`}
                  fill
                  className="object-cover"
                  unoptimized
                />
              </div>
            ) : (
              <div className="shrink-0 w-12 h-16 rounded bg-gray-100 dark:bg-gray-800" />
            )}
            <div className="min-w-0 flex-1">
              <p className="font-semibold leading-snug">{book.title}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{book.author}</p>
              <div className="flex flex-wrap gap-1 mt-2">
                {book.tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
            <button
              onClick={() => handleVote(book.id)}
              className="shrink-0 flex flex-col items-center gap-0.5 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-800 hover:border-gray-400 dark:hover:border-gray-600 transition-colors text-sm font-medium"
            >
              <span>+1</span>
              <span className="text-gray-400 dark:text-gray-500">{votes[book.id]}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function TagButton({
  children,
  active,
  onClick,
}: {
  children: React.ReactNode
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`text-sm px-3 py-1 rounded-full border transition-colors ${
        active
          ? "border-gray-900 bg-gray-900 text-white dark:border-white dark:bg-white dark:text-gray-900"
          : "border-gray-200 dark:border-gray-800 hover:border-gray-400 dark:hover:border-gray-600"
      }`}
    >
      {children}
    </button>
  )
}
