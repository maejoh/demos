"use client"

import { useState, useEffect } from "react"
import type { Book } from "@/lib/books"
import { FilterBarList, type FilterField, type ActiveFilter } from "./FilterBars"
import { BookList } from "./BookList"

function IntroText() {
  return (
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
  )
}

export default function BookShelf({ books, fetchError = null }: { books: Book[]; fetchError?: string | null }) {
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>(null)
  const [votes, setVotes] = useState<Record<string, number>>(
    Object.fromEntries(books.map((b) => [b.id, b.votes]))
  )

  useEffect(() => {
    if (fetchError) console.error("[BookShelf] Redis error:", fetchError)
  }, [fetchError])

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

  function handleTagClick(tag: string, field: FilterField) {
    setActiveFilter((prev) =>
      prev?.tag === tag && prev?.field === field ? null : { tag, field }
    )
  }

  function handleVote(id: string) {
    // TODO: replace with server action that persists to Redis
    setVotes((prev) => ({ ...prev, [id]: prev[id] + 1 }))
  }

  if (fetchError) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-16">
        <IntroText />
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Couldn&apos;t reach the book store right now. Try refreshing the page.
        </p>
      </div>
    )
  }

  if (books.length === 0) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-16">
        <IntroText />
        <p className="text-sm text-gray-500 dark:text-gray-400">
          The shelf is empty — no books have been added yet.
        </p>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-16">
      <IntroText />
      <FilterBarList
        allTags={allTags}
        allAiTags={allAiTags}
        allBundles={allBundles}
        activeFilter={activeFilter}
        onTagClick={handleTagClick}
        onClearFilter={() => setActiveFilter(null)}
      />
      <BookList books={visible} votes={votes} onVote={handleVote} />
    </div>
  )
}
