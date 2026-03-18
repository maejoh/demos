/**
 * Integration tests for BookShelf.
 *
 * These tests exercise state management: filter selection and vote counts.
 * Rendering details for individual components (tiles, filter bars) live in
 * their own focused test files.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import BookShelf from "@/app/components/BookShelf"
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

const books: Book[] = [
  makeBook({ id: "1", title: "Alpha", tags: ["JavaScript"] }),
  makeBook({ id: "2", title: "Beta",  tags: ["TypeScript"] }),
  makeBook({ id: "3", title: "Gamma", tags: ["JavaScript", "React"] }),
]

describe("BookShelf", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {})
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("renders all books on initial load", () => {
    render(<BookShelf books={books} />)
    expect(screen.getByText("Alpha")).toBeInTheDocument()
    expect(screen.getByText("Beta")).toBeInTheDocument()
    expect(screen.getByText("Gamma")).toBeInTheDocument()
  })

  it("filters to matching books when a tag is clicked", async () => {
    const user = userEvent.setup()
    render(<BookShelf books={books} />)

    await user.click(screen.getByRole("button", { name: "TypeScript" }))

    expect(screen.queryByText("Alpha")).not.toBeInTheDocument()
    expect(screen.getByText("Beta")).toBeInTheDocument()
    expect(screen.queryByText("Gamma")).not.toBeInTheDocument()
  })

  it("shows all books again when clicking the active tag a second time", async () => {
    const user = userEvent.setup()
    render(<BookShelf books={books} />)

    await user.click(screen.getByRole("button", { name: "JavaScript" }))
    await user.click(screen.getByRole("button", { name: "JavaScript" }))

    expect(screen.getByText("Alpha")).toBeInTheDocument()
    expect(screen.getByText("Beta")).toBeInTheDocument()
    expect(screen.getByText("Gamma")).toBeInTheDocument()
  })

  it("shows all books when the All button is clicked", async () => {
    const user = userEvent.setup()
    render(<BookShelf books={books} />)

    await user.click(screen.getByRole("button", { name: "TypeScript" }))
    await user.click(screen.getByRole("button", { name: "All" }))

    expect(screen.getByText("Alpha")).toBeInTheDocument()
    expect(screen.getByText("Beta")).toBeInTheDocument()
    expect(screen.getByText("Gamma")).toBeInTheDocument()
  })

  it("increments the vote count when +1 is clicked", async () => {
    const user = userEvent.setup()
    render(<BookShelf books={[makeBook({ votes: 42 })]} />)

    expect(screen.getByText("42")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /\+1/ }))
    expect(screen.getByText("43")).toBeInTheDocument()
  })

  it("shows an error notice and no book list when fetchError is set", () => {
    render(<BookShelf books={[]} fetchError="connection refused" />)
    expect(screen.getByText(/couldn't reach the book store/i)).toBeInTheDocument()
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument()
  })

  it("logs fetchError to console.error when set", () => {
    render(<BookShelf books={[]} fetchError="connection refused" />)
    expect(console.error).toHaveBeenCalledWith(
      expect.stringContaining("BookShelf"),
      expect.stringContaining("connection refused")
    )
  })

  it("shows an empty shelf notice and no book list when books is empty and no error", () => {
    render(<BookShelf books={[]} />)
    expect(screen.getByText(/the shelf is empty/i)).toBeInTheDocument()
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument()
  })
})
