"use client"

import { useState } from "react"
import Image from "next/image"
import type { Book } from "@/lib/books"
import { toTitleCase } from "@/lib/utils"

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

function BookHeader({ title, author, tags, ai_tags, humbleBundle, open, onToggle }: { title: string; author: string; tags: string[]; ai_tags?: string[]; humbleBundle?: string; open: boolean; onToggle: () => void }) {
  return (
    <div className="min-w-0 flex-1">
      <p className="font-semibold leading-snug">{title}</p>
      <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{author}</p>
      {humbleBundle && (
        <p className="hidden md:block text-xs text-gray-400 dark:text-gray-600 mt-0.5">{toTitleCase(humbleBundle)}</p>
      )}
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
      <button
        onClick={onToggle}
        className="flex items-center gap-1 mt-2 text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-600 hover:text-gray-600 dark:hover:text-gray-400 transition-colors"
      >
        <span className="italic">Details</span>
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`}>
          <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
    </div>
  )
}

const DESCRIPTION_TRUNCATION_THRESHOLD = 280

function BookDetails({ book }: { book: Book }) {
  const [expanded, setExpanded] = useState(false)
  const description = book.description || null
  const truncates = (description?.length ?? 0) > DESCRIPTION_TRUNCATION_THRESHOLD

  return (
    <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
      <div className="flex gap-4 mb-3 text-xs text-gray-400 dark:text-gray-600">
        {book.year !== null && <span>Published: {book.year}</span>}
        <span>ISBN: {book.isbn}</span>
      </div>
      <div className="px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-800">
        {description ? (
          <>
            <p className="text-xs text-gray-400 dark:text-gray-600 mb-1 italic">Description from Google Books:</p>
            <p className={`text-sm text-gray-600 dark:text-gray-400 leading-relaxed ${truncates && !expanded ? "line-clamp-4" : ""}`}>
              <span className="text-2xl text-gray-300 dark:text-gray-700 leading-none select-none align-top mr-0.5">&ldquo;</span>
              {description}
              <span className="text-2xl text-gray-300 dark:text-gray-700 leading-none select-none align-bottom ml-0.5">&rdquo;</span>
            </p>
          </>
        ) : (
          <p className="text-xs text-gray-400 dark:text-gray-600 italic">No description available from Google Books.</p>
        )}
        {truncates && (
          <button
            onClick={() => setExpanded((p) => !p)}
            className="mt-1 text-xs text-gray-400 dark:text-gray-600 hover:text-gray-600 dark:hover:text-gray-400 transition-colors"
          >
            {expanded ? "Show less" : "Show more"}
          </button>
        )}
      </div>
    </div>
  )
}

function VoteButton({ isbn, votes, voted, pending, onVote }: { isbn: string; votes: number; voted: boolean; pending: boolean; onVote: (isbn: string) => void }) {
  return (
    <button
      onClick={() => onVote(isbn)}
      disabled={pending}
      className={[
        "w-16 min-[375px]:w-24 md:w-auto shrink-0 flex flex-row md:flex-col items-center gap-2 md:gap-0.5 px-3 py-2 rounded-lg border transition-colors text-sm font-medium",
        pending
          ? "opacity-50 cursor-not-allowed border-gray-200 dark:border-gray-800"
          : voted
          ? "border-gray-500 dark:border-gray-400 bg-gray-50 dark:bg-gray-800 hover:border-gray-400 dark:hover:border-gray-500"
          : "border-gray-200 dark:border-gray-800 hover:border-gray-400 dark:hover:border-gray-600",
      ].join(" ")}
    >
      <span>+1</span>
      <span className="text-gray-400 dark:text-gray-500">{votes}</span>
    </button>
  )
}

type BookTileProps = {
  book: Book
  votes: number
  voted: boolean
  pending: boolean
  onVote: (isbn: string) => void
}

export function BookTile({ book, votes, voted, pending, onVote }: BookTileProps) {
  const [detailsOpen, setDetailsOpen] = useState(false)

  return (
    <li className="p-4 rounded-lg border border-gray-200 dark:border-gray-800">
      <div className="flex flex-col md:flex-row md:items-start gap-3 md:gap-4">
        <div className="flex gap-4 flex-1 min-w-0">
          <BookCover coverUrl={book.coverUrl} title={book.title} />
          <BookHeader
            title={book.title}
            author={book.author}
            tags={book.tags}
            ai_tags={book.ai_tags}
            humbleBundle={book.humbleBundle}
            open={detailsOpen}
            onToggle={() => setDetailsOpen((p) => !p)}
          />
        </div>
        <VoteButton isbn={book.isbn} votes={votes} voted={voted} pending={pending} onVote={onVote} />
      </div>
      {detailsOpen && <BookDetails book={book} />}
    </li>
  )
}
