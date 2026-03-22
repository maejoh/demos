/**
 * Unit tests for BookList.
 *
 * These tests cover list-level rendering. Individual tile behaviour lives
 * in BookTile.test.tsx.
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { BookList } from "@/app/components/BookList"
import type { Book } from "@/lib/books"

const makeBook = (overrides: Partial<Book> = {}): Book => ({
  id: "1",
  title: "Test Book",
  author: "Some Author",
  isbn: "9781234567890",
  year: 2020,
  tags: ["JavaScript"],
  description: "A test book",
  votes: 0,
  ...overrides,
})

const emptyVoteSets = { votedIsbns: new Set<string>(), pendingIsbns: new Set<string>() }

describe("BookList", () => {
  it("renders one list item per book", () => {
    const books = [
      makeBook({ id: "1", title: "Alpha" }),
      makeBook({ id: "2", title: "Beta" }),
      makeBook({ id: "3", title: "Gamma" }),
    ]
    render(<BookList books={books} votes={{ "1": 0, "2": 0, "3": 0 }} {...emptyVoteSets} onVote={vi.fn()} />)
    expect(screen.getAllByRole("listitem")).toHaveLength(3)
  })

  it("renders an empty list when books is empty", () => {
    const { container } = render(<BookList books={[]} votes={{}} {...emptyVoteSets} onVote={vi.fn()} />)
    expect(container.querySelector("ul")).toBeInTheDocument()
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument()
  })

  it("passes the correct vote count to each tile", () => {
    const book = makeBook({ id: "1", title: "Alpha" })
    render(<BookList books={[book]} votes={{ "9781234567890": 99 }} {...emptyVoteSets} onVote={vi.fn()} />)
    expect(screen.getByText("99")).toBeInTheDocument()
  })
})
