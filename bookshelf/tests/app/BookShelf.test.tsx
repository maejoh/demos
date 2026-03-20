/**
 * Integration tests for BookShelf.
 *
 * These tests exercise state management: filter selection and vote counts.
 * Rendering details for individual components (tiles, filter bars) live in
 * their own focused test files.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import BookShelf from "@/app/components/BookShelf"
import { castVote, removeVote } from "@/app/actions"
import type { Book } from "@/lib/books"

vi.mock("@/app/actions", () => ({
  castVote: vi.fn(),
  removeVote: vi.fn(),
}))

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

// ai_tags need count >= 5 to appear in the sidebar — give each tag 5 books
const makeTaggedBooks = (): Book[] => [
  makeBook({ id: "1", isbn: "0000000000001", title: "Alpha", ai_tags: ["Python"] }),
  makeBook({ id: "2", isbn: "0000000000002", title: "Beta",  ai_tags: ["TypeScript"] }),
  makeBook({ id: "3", isbn: "0000000000003", title: "Gamma", ai_tags: ["Python", "TypeScript"] }),
  makeBook({ id: "4", isbn: "0000000000004", title: "Delta", ai_tags: ["Python"] }),
  makeBook({ id: "5", isbn: "0000000000005", title: "Epsilon", ai_tags: ["Python"] }),
  makeBook({ id: "6", isbn: "0000000000006", title: "Zeta",  ai_tags: ["Python"] }),
  makeBook({ id: "7", isbn: "0000000000007", title: "Eta",   ai_tags: ["TypeScript"] }),
  makeBook({ id: "8", isbn: "0000000000008", title: "Theta", ai_tags: ["TypeScript"] }),
  makeBook({ id: "9", isbn: "0000000000009", title: "Iota",  ai_tags: ["TypeScript"] }),
  makeBook({ id: "10", isbn: "0000000000010", title: "Kappa", ai_tags: ["TypeScript"] }),
]

describe("BookShelf", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {})
    vi.mocked(castVote).mockResolvedValue(undefined)
    vi.mocked(removeVote).mockResolvedValue(undefined)
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("renders all books on initial load", () => {
    render(<BookShelf books={makeTaggedBooks()} />)
    expect(screen.getByText("Alpha")).toBeInTheDocument()
    expect(screen.getByText("Beta")).toBeInTheDocument()
    expect(screen.getByText("Gamma")).toBeInTheDocument()
  })

  it("filters to books matching a checked tag", async () => {
    const user = userEvent.setup()
    render(<BookShelf books={makeTaggedBooks()} />)

    await user.click(screen.getByRole("checkbox", { name: "TypeScript" }))

    // Alpha has only Python — should be hidden
    expect(screen.queryByText("Alpha")).not.toBeInTheDocument()
    // Beta, Gamma, Eta, Theta, Iota, Kappa have TypeScript
    expect(screen.getByText("Beta")).toBeInTheDocument()
    expect(screen.getByText("Gamma")).toBeInTheDocument()
  })

  it("shows all books again when the active tag is unchecked", async () => {
    const user = userEvent.setup()
    render(<BookShelf books={makeTaggedBooks()} />)

    await user.click(screen.getByRole("checkbox", { name: "TypeScript" }))
    await user.click(screen.getByRole("checkbox", { name: "TypeScript" }))

    expect(screen.getByText("Alpha")).toBeInTheDocument()
    expect(screen.getByText("Beta")).toBeInTheDocument()
    expect(screen.getByText("Gamma")).toBeInTheDocument()
  })

  it("hides books with no ai_tags field when an ai tag filter is active", async () => {
    const user = userEvent.setup()
    render(<BookShelf books={[
      ...makeTaggedBooks(),
      makeBook({ id: "99", isbn: "9999999999999", title: "Untagged Book" }),
    ]} />)

    await user.click(screen.getByRole("checkbox", { name: "Python" }))

    expect(screen.queryByText("Untagged Book")).not.toBeInTheDocument()
  })

  it("applies OR logic within a category — shows books matching either tag", async () => {
    const user = userEvent.setup()
    render(<BookShelf books={makeTaggedBooks()} />)

    await user.click(screen.getByRole("checkbox", { name: "Python" }))
    await user.click(screen.getByRole("checkbox", { name: "TypeScript" }))

    // Alpha has Python, Beta has TypeScript, Gamma has both — all should show
    expect(screen.getByText("Alpha")).toBeInTheDocument()
    expect(screen.getByText("Beta")).toBeInTheDocument()
    expect(screen.getByText("Gamma")).toBeInTheDocument()
  })

  it("applies AND logic across categories — book must match all active categories", async () => {
    const user = userEvent.setup()
    // Alpha: Python + Pack A, Beta: Python + Pack B, plus filler to hit the >= 5 threshold
    const crossCategoryBooks: Book[] = [
      makeBook({ id: "1", isbn: "1000000000001", title: "Alpha", ai_tags: ["Python"], humbleBundle: "Pack A" }),
      makeBook({ id: "2", isbn: "1000000000002", title: "Beta",  ai_tags: ["Python"], humbleBundle: "Pack B" }),
      makeBook({ id: "3", isbn: "1000000000003", title: "Gamma", ai_tags: ["Python"] }),
      makeBook({ id: "4", isbn: "1000000000004", title: "Delta", ai_tags: ["Python"] }),
      makeBook({ id: "5", isbn: "1000000000005", title: "Epsilon", ai_tags: ["Python"] }),
    ]
    render(<BookShelf books={crossCategoryBooks} />)

    await user.click(screen.getByRole("checkbox", { name: "Python" }))
    await user.click(screen.getByRole("checkbox", { name: "Pack A" }))

    // Only Alpha has both Python and Pack A
    expect(screen.getByText("Alpha")).toBeInTheDocument()
    expect(screen.queryByText("Beta")).not.toBeInTheDocument()
    expect(screen.queryByText("Gamma")).not.toBeInTheDocument()
  })

  it("shows all books when clear all is clicked", async () => {
    const user = userEvent.setup()
    render(<BookShelf books={makeTaggedBooks()} />)

    await user.click(screen.getByRole("checkbox", { name: "TypeScript" }))
    await user.click(screen.getByRole("button", { name: /clear all/i }))

    expect(screen.getByText("Alpha")).toBeInTheDocument()
    expect(screen.getByText("Beta")).toBeInTheDocument()
    expect(screen.getByText("Gamma")).toBeInTheDocument()
  })

  it("shows only the first 24 books initially when there are more than 24", () => {
    const manyBooks = Array.from({ length: 25 }, (_, i) =>
      makeBook({ id: String(i), isbn: String(i).padStart(13, "0"), title: `Book ${String(i).padStart(2, "0")}` })
    )
    render(<BookShelf books={manyBooks} />)
    expect(screen.getAllByRole("listitem")).toHaveLength(24)
    expect(screen.getByRole("button", { name: /load more/i })).toBeInTheDocument()
  })

  it("shows remaining books and removes the button after load more is clicked", async () => {
    const user = userEvent.setup()
    const manyBooks = Array.from({ length: 25 }, (_, i) =>
      makeBook({ id: String(i), isbn: String(i).padStart(13, "0"), title: `Book ${String(i).padStart(2, "0")}` })
    )
    render(<BookShelf books={manyBooks} />)
    await user.click(screen.getByRole("button", { name: /load more/i }))
    expect(screen.getAllByRole("listitem")).toHaveLength(25)
    expect(screen.queryByRole("button", { name: /load more/i })).not.toBeInTheDocument()
  })

  it("increments the vote count when +1 is clicked", async () => {
    const user = userEvent.setup()
    render(<BookShelf books={[makeBook({ votes: 42 })]} />)

    expect(screen.getByText("42")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /\+1/ }))
    expect(screen.getByText("43")).toBeInTheDocument()
  })

  it("keeps the incremented count after castVote succeeds", async () => {
    const user = userEvent.setup()
    render(<BookShelf books={[makeBook({ votes: 5 })]} />)

    await user.click(screen.getByRole("button", { name: /\+1/ }))
    await waitFor(() => expect(castVote).toHaveBeenCalled())
    expect(screen.getByText("6")).toBeInTheDocument()
  })

  it("rolls back the vote count when castVote fails", async () => {
    vi.mocked(castVote).mockRejectedValue(new Error("network error"))
    const user = userEvent.setup()
    render(<BookShelf books={[makeBook({ votes: 5 })]} />)

    await user.click(screen.getByRole("button", { name: /\+1/ }))
    await waitFor(() => expect(screen.getByText("5")).toBeInTheDocument())
  })

  it("shows a vote error notice when castVote fails", async () => {
    vi.mocked(castVote).mockRejectedValue(new Error("network error"))
    const user = userEvent.setup()
    render(<BookShelf books={[makeBook({ votes: 5 })]} />)

    await user.click(screen.getByRole("button", { name: /\+1/ }))
    await waitFor(() => expect(screen.getByText(/couldn't save that vote/i)).toBeInTheDocument())
  })

  it("disables the vote button while an action is in-flight", async () => {
    const user = userEvent.setup()
    let resolve: () => void
    vi.mocked(castVote).mockReturnValue(new Promise<void>((r) => { resolve = r }))
    render(<BookShelf books={[makeBook({ votes: 5 })]} />)

    const button = screen.getByRole("button", { name: /\+1/ })
    expect(button).not.toBeDisabled()

    user.click(button)
    await waitFor(() => expect(button).toBeDisabled())

    resolve!()
    await waitFor(() => expect(button).not.toBeDisabled())
  })

  it("decrements the vote count when a voted book is clicked again", async () => {
    const user = userEvent.setup()
    render(<BookShelf books={[makeBook({ votes: 5 })]} />)

    await user.click(screen.getByRole("button", { name: /\+1/ }))
    await waitFor(() => expect(castVote).toHaveBeenCalled())
    await user.click(screen.getByRole("button", { name: /\+1/ }))
    await waitFor(() => expect(removeVote).toHaveBeenCalled())
    expect(screen.getByText("5")).toBeInTheDocument()
  })

  it("rolls back the vote count when removeVote fails", async () => {
    vi.mocked(removeVote).mockRejectedValue(new Error("network error"))
    const user = userEvent.setup()
    render(<BookShelf books={[makeBook({ votes: 5 })]} />)

    await user.click(screen.getByRole("button", { name: /\+1/ }))
    await waitFor(() => expect(castVote).toHaveBeenCalled())
    await user.click(screen.getByRole("button", { name: /\+1/ }))
    await waitFor(() => expect(screen.getByText("6")).toBeInTheDocument())
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

  describe("sorting", () => {
    it("sorts by votes ascending when Votes is clicked", async () => {
      const user = userEvent.setup()
      render(<BookShelf books={[
        makeBook({ isbn: "0000000000001", title: "High Votes Book", votes: 10 }),
        makeBook({ isbn: "0000000000002", title: "Low Votes Book", votes: 1 }),
      ]} />)

      await user.click(screen.getByRole("button", { name: /^votes$/i }))

      const items = screen.getAllByRole("listitem")
      expect(items[0]).toHaveTextContent("Low Votes Book")
      expect(items[1]).toHaveTextContent("High Votes Book")
    })

    it("reverses sort order when the active field is clicked again", async () => {
      const user = userEvent.setup()
      render(<BookShelf books={[
        makeBook({ isbn: "0000000000001", title: "Low Votes Book", votes: 1 }),
        makeBook({ isbn: "0000000000002", title: "High Votes Book", votes: 10 }),
      ]} />)

      await user.click(screen.getByRole("button", { name: /^votes$/i }))
      await user.click(screen.getByRole("button", { name: /votes.*↑/i }))

      const items = screen.getAllByRole("listitem")
      expect(items[0]).toHaveTextContent("High Votes Book")
      expect(items[1]).toHaveTextContent("Low Votes Book")
    })

    it("sorts by humbleBundle alphabetically", async () => {
      const user = userEvent.setup()
      const { container } = render(<BookShelf books={[
        makeBook({ isbn: "0000000000001", title: "Book from Zeta", humbleBundle: "Zeta Pack" }),
        makeBook({ isbn: "0000000000002", title: "Book from Alpha", humbleBundle: "Alpha Pack" }),
      ]} />)

      await user.click(screen.getByRole("button", { name: /^bundle$/i }))

      // scope to the book list only — the sidebar also renders bundle names as <li> items
      const bookList = container.querySelector("ul.space-y-4") as HTMLElement
      const items = within(bookList).getAllByRole("listitem")
      expect(items[0]).toHaveTextContent("Book from Alpha")
      expect(items[1]).toHaveTextContent("Book from Zeta")
    })

    it("sorts books without a humbleBundle to the end when sorting by bundle", async () => {
      const user = userEvent.setup()
      const { container } = render(<BookShelf books={[
        makeBook({ isbn: "0000000000001", title: "No Bundle A" }),
        makeBook({ isbn: "0000000000002", title: "No Bundle B" }),
        makeBook({ isbn: "0000000000003", title: "Zeta Book", humbleBundle: "Zeta Pack" }),
        makeBook({ isbn: "0000000000004", title: "Alpha Book", humbleBundle: "Alpha Pack" }),
      ]} />)

      await user.click(screen.getByRole("button", { name: /^bundle$/i }))

      // two no-bundle books force the comparator to run with both a.humbleBundle
      // and b.humbleBundle falsy, covering all branches of the ternary
      const bookList = container.querySelector("ul.space-y-4") as HTMLElement
      const items = within(bookList).getAllByRole("listitem")
      expect(items[0]).toHaveTextContent("Alpha Book")
      expect(items[1]).toHaveTextContent("Zeta Book")
      expect(items[2]).toHaveTextContent("No Bundle")
      expect(items[3]).toHaveTextContent("No Bundle")
    })

    it("toggles sort direction back to ascending when the active field is clicked a third time", async () => {
      const user = userEvent.setup()
      render(<BookShelf books={[
        makeBook({ isbn: "0000000000001", title: "Low Votes Book", votes: 1 }),
        makeBook({ isbn: "0000000000002", title: "High Votes Book", votes: 10 }),
      ]} />)

      await user.click(screen.getByRole("button", { name: /^votes$/i }))   // asc
      await user.click(screen.getByRole("button", { name: /votes.*↑/i }))  // desc
      await user.click(screen.getByRole("button", { name: /votes.*↓/i }))  // back to asc

      const items = screen.getAllByRole("listitem")
      expect(items[0]).toHaveTextContent("Low Votes Book")
      expect(items[1]).toHaveTextContent("High Votes Book")
    })
  })

  it("opens the sidebar when the mobile filters toggle is clicked", async () => {
    const user = userEvent.setup()
    const { container } = render(<BookShelf books={[makeBook()]} />)

    const content = container.querySelector(".md\\:block")
    expect(content).toHaveClass("hidden")

    await user.click(screen.getByRole("button", { name: /filters/i }))

    expect(content).not.toHaveClass("hidden")
  })
})
