"use client"

import { useState } from "react"
import Image from "next/image"
import type { Book } from "@/lib/books"

export default function BookShelf({ books }: { books: Book[] }) {
  const [activeFilter, setActiveFilter] = useState<{ tag: string; field: "tags" | "ai_tags" | "humbleBundle" } | null>(null)
  const [votes, setVotes] = useState<Record<string, number>>(
    Object.fromEntries(books.map((b) => [b.id, b.votes]))
  )

  const allTags = Array.from(new Set(books.flatMap((b) => b.tags))).sort()
  const aiTagCounts = books.flatMap((b) => b.ai_tags ?? []).reduce<Record<string, number>>((acc, t) => ({ ...acc, [t]: (acc[t] ?? 0) + 1 }), {})
  const allAiTags = Object.keys(aiTagCounts).filter((t) => aiTagCounts[t] >= 5).sort()
  const allBundles = Array.from(new Set(books.map((b) => b.humbleBundle).filter(Boolean))).sort() as string[]
  const visible = activeFilter
    ? books.filter((b) =>
        activeFilter.field === "humbleBundle"
          ? b.humbleBundle === activeFilter.tag
          : (b[activeFilter.field] ?? []).includes(activeFilter.tag)
      )
    : books

  function handleTagClick(tag: string, field: "tags" | "ai_tags" | "humbleBundle") {
    setActiveFilter((prev) =>
      prev?.tag === tag && prev?.field === field ? null : { tag, field }
    )
  }

  function handleVote(id: string) {
    // TODO: replace with server action that persists to Redis
    setVotes((prev) => ({ ...prev, [id]: prev[id] + 1 }))
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-16">
      <header className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight mb-2">My Technical Library</h1>
        <p className="text-gray-500 dark:text-gray-400">
          A browsable collection of publications related to programming — AI, LLMs, web dev, systems engineering and architecture, math, and more. Upvote anything that looks interesting to you too! Vote counts are persisted and public, so they reflect the collective interest of everyone who has visited so far.
        </p>
        <p className="text-sm text-gray-400 dark:text-gray-500 mt-3">
          There&apos;s a gremlin inside me that buys tech books whenever Humble Bundle drops a software book bundle. These are all real books I&apos;ve purchased over the last 2 years.{" "}
          </p><p className="text-sm text-gray-500 dark:text-gray-500 mt-3">
          <a
            href="https://github.com/maejoh/demos"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            View on GitHub →
          </a>
        </p>
      </header>

      <div className="space-y-3 mb-8">
        <div className="hidden flex-wrap gap-2 items-center">
          <span className="text-xs text-gray-400 dark:text-gray-500 w-12 shrink-0">Topics</span>
          <TagButton active={activeFilter === null} onClick={() => setActiveFilter(null)}>
            All
          </TagButton>
          {allTags.map((tag) => (
            <TagButton
              key={tag}
              active={activeFilter?.tag === tag && activeFilter?.field === "tags"}
              onClick={() => handleTagClick(tag, "tags")}
            >
              {tag}
            </TagButton>
          ))}
        </div>
        {allAiTags.length > 0 && (
          <div className="flex flex-wrap gap-2 items-center">
            <span className="text-xs text-gray-400 dark:text-gray-500 w-12 shrink-0">AI tags</span>
            {allAiTags.map((tag) => (
              <TagButton
                key={tag}
                active={activeFilter?.tag === tag && activeFilter?.field === "ai_tags"}
                onClick={() => handleTagClick(tag, "ai_tags")}
              >
                {tag}
              </TagButton>
            ))}
          </div>
        )}
        {allBundles.length > 0 && (
          <div className="flex flex-wrap gap-2 items-center">
            <span className="text-xs text-gray-400 dark:text-gray-500 w-12 shrink-0">Bundle</span>
            <TagButton active={activeFilter === null} onClick={() => setActiveFilter(null)}>
              All
            </TagButton>
            {allBundles.map((bundle) => (
              <TagButton
                key={bundle}
                active={activeFilter?.tag === bundle && activeFilter?.field === "humbleBundle"}
                onClick={() => handleTagClick(bundle, "humbleBundle")}
              >
                {bundle}
              </TagButton>
            ))}
          </div>
        )}
      </div>

      <ul className="space-y-4">
        {visible.map((book) => (
          <li
            key={book.id}
            className="flex items-start justify-between gap-4 p-4 rounded-lg border border-gray-200 dark:border-gray-800"
          >
            {book.coverUrl ? (
              <div className="shrink-0 w-24 h-30 relative rounded overflow-hidden bg-gray-100 dark:bg-gray-800">
                <Image
                  src={book.coverUrl}
                  alt={`Cover of ${book.title}`}
                  fill
                  className="object-contain"
                  unoptimized
                />
              </div>
            ) : (
              <div className="shrink-0 w-24 h-30 rounded bg-gray-100 dark:bg-gray-800" />
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
                {book.ai_tags?.map((tag) => (
                  <span
                    key={tag}
                    className="text-xs px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-300"
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
