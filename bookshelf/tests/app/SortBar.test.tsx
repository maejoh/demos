/**
 * Unit tests for SortBar.
 *
 * Covers rendering of sort options, click dispatch, and direction indicator display.
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { SortBar } from "@/app/components/SortBar"

const defaultProps = {
  sortField: "title" as const,
  sortDir: "asc" as const,
  onSort: vi.fn(),
}

describe("SortBar", () => {
  it("renders a button for each sort option", () => {
    render(<SortBar {...defaultProps} />)
    expect(screen.getByRole("button", { name: /title/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /author/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /bundle/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /votes/i })).toBeInTheDocument()
  })

  it("calls onSort with the correct field when a button is clicked", async () => {
    const user = userEvent.setup()
    const onSort = vi.fn()
    render(<SortBar {...defaultProps} onSort={onSort} />)

    await user.click(screen.getByRole("button", { name: /author/i }))
    expect(onSort).toHaveBeenCalledWith("author")
  })

  it("shows ascending indicator on the active sort field", () => {
    render(<SortBar {...defaultProps} sortField="title" sortDir="asc" />)
    expect(screen.getByRole("button", { name: /title.*↑/i })).toBeInTheDocument()
  })

  it("shows descending indicator on the active sort field", () => {
    render(<SortBar {...defaultProps} sortField="title" sortDir="desc" />)
    expect(screen.getByRole("button", { name: /title.*↓/i })).toBeInTheDocument()
  })

  it("does not show a direction indicator on inactive fields", () => {
    render(<SortBar {...defaultProps} sortField="title" sortDir="asc" />)
    expect(screen.getByRole("button", { name: "Author" })).toBeInTheDocument()
  })
})
