"use client"

import { useState, useEffect } from "react"
import type { Book } from "@/lib/books"
import { castVote, removeVote } from "@/app/actions"
import { toTitleCase } from "@/lib/utils"
import { FilterSidebar, type FilterField, type ActiveFilters } from "./FilterSidebar"
import { BookList } from "./BookList"
import { SortBar, type SortField, type SortDir } from "./SortBar"
import { ThemeToggle } from "./ThemeToggle"

const PAGE_SIZE = 24

function IntroText() {
  return (
    <header className="mb-10">
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-3xl font-bold tracking-tight">My Technical Library</h1>
        <ThemeToggle />
      </div>
      <p className="text-gray-500 dark:text-gray-400">
        A browsable collection of publications related to comp sci — AI, web dev, software architecture, and more. What should I read next?
      </p>
      <p className="text-sm text-gray-400 dark:text-gray-500 mt-3">
        I can&apos;t resist a good Humble Bundle, and that especially includes tech books. Below you will find an interface for browsing all the ones I&apos;ve bought so far, between the various bundles they&apos;ve put out over the past few years. Some of these titles I&apos;ve already started reading, but many are just waiting for a reason! Cast your votes to help me hone in even more on what topics are most relevant to the peers and recruiters viewing my portfolio.{" "}
      </p>
      <p className="text-sm text-gray-500 dark:text-gray-500 mt-3">
        Note: The primary purpose of this app is as a portfolio piece.{"  "}
        <a
          href="https://github.com/maejoh/demos"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
        >
          View it on GitHub →
        </a>
      </p>
    </header>
  )
}

export default function BookShelf({ books, fetchError = null }: { books: Book[]; fetchError?: string | null }) {
  const [activeFilters, setActiveFilters] = useState<ActiveFilters>({})
  const [displayCount, setDisplayCount] = useState(PAGE_SIZE)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [votes, setVotes] = useState<Record<string, number>>(
    Object.fromEntries(books.map((b) => [b.isbn, b.votes]))
  )
  const [voteError, setVoteError] = useState(false)
  const [votedIsbns, setVotedIsbns] = useState<Set<string>>(new Set())
  const [pendingIsbns, setPendingIsbns] = useState<Set<string>>(new Set())
  const [sortField, setSortField] = useState<SortField>("title")
  const [sortDir, setSortDir] = useState<SortDir>("asc")

  useEffect(() => {
    if (fetchError) console.error("[BookShelf] Redis error:", fetchError)
  }, [fetchError])

  const aiTagCounts = books
    .flatMap((b) => b.ai_tags ?? [])
    .reduce<Record<string, number>>((acc, t) => ({ ...acc, [t]: (acc[t] ?? 0) + 1 }), {})
  const allAiTags = Object.keys(aiTagCounts).filter((t) => aiTagCounts[t] >= 5).sort()
  const allBundles = Array.from(
    new Set(books.map((b) => b.humbleBundle ? toTitleCase(b.humbleBundle) : undefined).filter(Boolean))
  ).sort() as string[]

  const visible = books.filter((book) =>
    (Object.entries(activeFilters) as [FilterField, string[]][]).every(([field, tags]) => {
      if (field === "humbleBundle") return tags.includes(book.humbleBundle ? toTitleCase(book.humbleBundle) : "")
      return (book[field] ?? []).some((tag) => tags.includes(tag))
    })
  )

  const sorted = [...visible].sort((a, b) => {
    let cmp = 0
    if (sortField === "votes") {
      cmp = votes[a.isbn] - votes[b.isbn]
    } else if (sortField === "humbleBundle") {
      const aVal = a.humbleBundle ? toTitleCase(a.humbleBundle) : "\uffff"
      const bVal = b.humbleBundle ? toTitleCase(b.humbleBundle) : "\uffff"
      cmp = aVal.localeCompare(bVal)
    } else {
      cmp = (a[sortField] as string).localeCompare(b[sortField] as string)
    }
    return sortDir === "asc" ? cmp : -cmp
  })

  function handleSort(field: SortField) {
    if (field === sortField) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"))
    } else {
      setSortField(field)
      setSortDir("asc")
    }
    setDisplayCount(PAGE_SIZE)
  }

  function handleToggleFilter(tag: string, field: FilterField) {
    setActiveFilters((prev) => {
      const current = prev[field] ?? []
      const updated = current.includes(tag)
        ? current.filter((t) => t !== tag)
        : [...current, tag]
      if (updated.length === 0) {
        const next = { ...prev }
        delete next[field]
        return next
      }
      return { ...prev, [field]: updated }
    })
    setDisplayCount(PAGE_SIZE)
  }

  function handleClearAll() {
    setActiveFilters({})
    setDisplayCount(PAGE_SIZE)
  }

  async function handleVote(isbn: string) {
    setVoteError(false)
    const isVoted = votedIsbns.has(isbn)
    const delta = isVoted ? -1 : 1
    setPendingIsbns((prev) => new Set(prev).add(isbn))
    setVotes((prev) => ({ ...prev, [isbn]: prev[isbn] + delta }))
    try {
      if (isVoted) {
        await removeVote(isbn)
        setVotedIsbns((prev) => { const next = new Set(prev); next.delete(isbn); return next })
      } else {
        await castVote(isbn)
        setVotedIsbns((prev) => new Set(prev).add(isbn))
      }
    } catch (err) {
      console.error("[BookShelf] Vote failed:", err)
      setVotes((prev) => ({ ...prev, [isbn]: prev[isbn] - delta }))
      setVoteError(true)
    } finally {
      setPendingIsbns((prev) => { const next = new Set(prev); next.delete(isbn); return next })
    }
  }

  if (fetchError) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-16">
        <IntroText />
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Couldn&apos;t reach the book store right now. Try refreshing the page.
        </p>
      </div>
    )
  }

  if (books.length === 0) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-16">
        <IntroText />
        <p className="text-sm text-gray-500 dark:text-gray-400">
          The shelf is empty — no books have been added yet.
        </p>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-16">
      <IntroText />
      <div className="flex flex-col md:flex-row gap-10 items-start">
        <FilterSidebar
          allAiTags={allAiTags}
          allBundles={allBundles}
          activeFilters={activeFilters}
          onToggle={handleToggleFilter}
          onClearAll={handleClearAll}
          isOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen((p) => !p)}
        />
        <div className="flex-1 min-w-0 border-2 border-gray-500 dark:border-gray-800 rounded-lg">
          <div className="p-6">
            {voteError && (
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                Couldn&apos;t save that vote — your count has been rolled back.
              </p>
            )}
            <SortBar sortField={sortField} sortDir={sortDir} onSort={handleSort} />
            <BookList books={sorted.slice(0, displayCount)} votes={votes} votedIsbns={votedIsbns} pendingIsbns={pendingIsbns} onVote={handleVote} />
            {sorted.length > displayCount && (
              <button
                onClick={() => setDisplayCount((p) => p + PAGE_SIZE)}
                className="mt-6 w-full py-2 text-sm text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-800 rounded-lg hover:border-gray-400 dark:hover:border-gray-600 transition-colors"
              >
                Load more ({sorted.length - displayCount} remaining)
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
