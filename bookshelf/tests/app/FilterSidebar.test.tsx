/**
 * Unit tests for FilterSidebar and FilterSection.
 *
 * These tests cover rendering, checkbox state, interaction callbacks, the
 * mobile toggle, and the clear-all button. Integration with BookShelf
 * (filtered results) lives in BookShelf.test.tsx.
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { FilterSidebar } from "@/app/components/FilterSidebar"
import type { ActiveFilters } from "@/app/components/FilterSidebar"

const defaultProps = {
  allAiTags: ["Python", "Machine Learning"],
  allBundles: ["Pack A", "Pack B"],
  activeFilters: {} as ActiveFilters,
  onToggle: vi.fn(),
  onClearAll: vi.fn(),
  isOpen: false,
  onToggleSidebar: vi.fn(),
}

describe("FilterSidebar", () => {
  describe("FilterSection rendering", () => {
    it("renders a checkbox for each ai tag", () => {
      render(<FilterSidebar {...defaultProps} />)
      expect(screen.getByRole("checkbox", { name: "Python" })).toBeInTheDocument()
      expect(screen.getByRole("checkbox", { name: "Machine Learning" })).toBeInTheDocument()
    })

    it("renders a checkbox for each bundle", () => {
      render(<FilterSidebar {...defaultProps} />)
      expect(screen.getByRole("checkbox", { name: "Pack A" })).toBeInTheDocument()
      expect(screen.getByRole("checkbox", { name: "Pack B" })).toBeInTheDocument()
    })

    it("does not render a section when its tag list is empty", () => {
      render(<FilterSidebar {...defaultProps} allAiTags={[]} />)
      expect(screen.queryByText("AI Tags")).not.toBeInTheDocument()
    })
  })

  describe("checkbox state", () => {
    it("renders active tags as checked", () => {
      render(
        <FilterSidebar
          {...defaultProps}
          activeFilters={{ ai_tags: ["Python"] }}
        />
      )
      expect(screen.getByRole("checkbox", { name: "Python" })).toBeChecked()
      expect(screen.getByRole("checkbox", { name: "Machine Learning" })).not.toBeChecked()
    })

    it("calls onToggle with tag and field when a checkbox is clicked", async () => {
      const user = userEvent.setup()
      const onToggle = vi.fn()
      render(<FilterSidebar {...defaultProps} onToggle={onToggle} />)

      await user.click(screen.getByRole("checkbox", { name: "Python" }))
      expect(onToggle).toHaveBeenCalledWith("Python", "ai_tags")
    })

    it("calls onToggle with humbleBundle field for bundle checkboxes", async () => {
      const user = userEvent.setup()
      const onToggle = vi.fn()
      render(<FilterSidebar {...defaultProps} onToggle={onToggle} />)

      await user.click(screen.getByRole("checkbox", { name: "Pack A" }))
      expect(onToggle).toHaveBeenCalledWith("Pack A", "humbleBundle")
    })
  })

  describe("clear all", () => {
    it("does not show clear all when no filters are active", () => {
      render(<FilterSidebar {...defaultProps} activeFilters={{}} />)
      expect(screen.queryByRole("button", { name: /clear all/i })).not.toBeInTheDocument()
    })

    it("shows clear all when at least one filter is active", () => {
      render(<FilterSidebar {...defaultProps} activeFilters={{ ai_tags: ["Python"] }} />)
      expect(screen.getByRole("button", { name: /clear all/i })).toBeInTheDocument()
    })

    it("calls onClearAll when clear all is clicked", async () => {
      const user = userEvent.setup()
      const onClearAll = vi.fn()
      render(
        <FilterSidebar
          {...defaultProps}
          activeFilters={{ ai_tags: ["Python"] }}
          onClearAll={onClearAll}
        />
      )
      await user.click(screen.getByRole("button", { name: /clear all/i }))
      expect(onClearAll).toHaveBeenCalled()
    })
  })

  describe("mobile toggle", () => {
    it("renders the mobile toggle button", () => {
      render(<FilterSidebar {...defaultProps} />)
      expect(screen.getByRole("button", { name: /filters/i })).toBeInTheDocument()
    })

    it("shows the active filter count in the toggle label", () => {
      render(
        <FilterSidebar
          {...defaultProps}
          activeFilters={{ ai_tags: ["Python", "Machine Learning"], humbleBundle: ["Pack A"] }}
        />
      )
      expect(screen.getByRole("button", { name: /filters · 3/i })).toBeInTheDocument()
    })

    it("calls onToggleSidebar when the toggle button is clicked", async () => {
      const user = userEvent.setup()
      const onToggleSidebar = vi.fn()
      render(<FilterSidebar {...defaultProps} onToggleSidebar={onToggleSidebar} />)
      await user.click(screen.getByRole("button", { name: /filters/i }))
      expect(onToggleSidebar).toHaveBeenCalled()
    })

    it("applies the hidden class to sidebar content when isOpen is false", () => {
      const { container } = render(<FilterSidebar {...defaultProps} isOpen={false} />)
      // the content div is hidden on mobile when closed
      const content = container.querySelector(".md\\:block")
      expect(content).toHaveClass("hidden")
    })

    it("shows sidebar content when isOpen is true", () => {
      const { container } = render(<FilterSidebar {...defaultProps} isOpen={true} />)
      const content = container.querySelector(".md\\:block")
      expect(content).not.toHaveClass("hidden")
    })
  })
})
