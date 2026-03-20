/**
 * Unit tests for BookTile and its sub-components (BookCover, BookHeader, VoteButton).
 *
 * These tests cover what a single book card renders and how it responds to
 * interaction. List-level behaviour lives in BookList.test.tsx.
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { BookTile } from "@/app/components/BookTile"
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

const defaultProps = { voted: false, pending: false, onVote: vi.fn() }

describe("BookTile", () => {
  describe("BookHeader", () => {
    it("renders the book title and author", () => {
      render(<BookTile book={makeBook()} votes={0} {...defaultProps} />)
      expect(screen.getByText("Test Book")).toBeInTheDocument()
      expect(screen.getByText("Some Author")).toBeInTheDocument()
    })

    it("renders topic tags as chips", () => {
      render(<BookTile book={makeBook({ tags: ["Python", "Databases"] })} votes={0} {...defaultProps} />)
      expect(screen.getByText("Python")).toBeInTheDocument()
      expect(screen.getByText("Databases")).toBeInTheDocument()
    })

    it("renders AI tags when present", () => {
      render(<BookTile book={makeBook({ ai_tags: ["Machine Learning"] })} votes={0} {...defaultProps} />)
      expect(screen.getByText("Machine Learning")).toBeInTheDocument()
    })

    it("renders no AI tag chips when ai_tags is absent", () => {
      const { container } = render(<BookTile book={makeBook({ ai_tags: undefined })} votes={0} {...defaultProps} />)
      // blue chip class is only used for AI tags
      expect(container.querySelector(".bg-blue-50")).not.toBeInTheDocument()
    })
  })

  describe("BookCover", () => {
    it("renders a cover image when coverUrl is present", () => {
      render(<BookTile book={makeBook({ title: "Covered", coverUrl: "/covers/test.jpg" })} votes={0} {...defaultProps} />)
      expect(screen.getByAltText("Cover of Covered")).toBeInTheDocument()
    })

    it("renders a placeholder div when coverUrl is absent", () => {
      render(<BookTile book={makeBook({ coverUrl: undefined })} votes={0} {...defaultProps} />)
      expect(screen.queryByRole("img")).not.toBeInTheDocument()
    })
  })

  describe("VoteButton", () => {
    it("displays the current vote count", () => {
      render(<BookTile book={makeBook()} votes={17} {...defaultProps} />)
      expect(screen.getByText("17")).toBeInTheDocument()
    })

    it("calls onVote with the book id when clicked", async () => {
      const user = userEvent.setup()
      const onVote = vi.fn()
      render(<BookTile book={makeBook({ isbn: "9780000000042" })} votes={0} voted={false} pending={false} onVote={onVote} />)

      await user.click(screen.getByRole("button", { name: /\+1/ }))

      expect(onVote).toHaveBeenCalledWith("9780000000042")
    })
  })
})
