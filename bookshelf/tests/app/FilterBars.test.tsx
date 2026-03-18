/**
 * Unit tests for FilterBar and FilterBarList.
 *
 * These tests cover rendering and active-state logic for the filter UI.
 * State changes that result from clicking (e.g. books being filtered) are
 * tested at the BookShelf level.
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { FilterBar, FilterBarList } from "@/app/components/FilterBars"
import type { ActiveFilter } from "@/app/components/FilterBars"

describe("FilterBar", () => {
  it("renders a button for each tag", () => {
    render(
      <FilterBar label="AI tags" tags={["Python", "Databases"]} field="ai_tags" activeFilter={null} onTagClick={vi.fn()} />
    )
    expect(screen.getByRole("button", { name: "Python" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Databases" })).toBeInTheDocument()
  })

  it("renders an All button when onClearFilter is provided", () => {
    render(
      <FilterBar label="Bundle" tags={["Pack A"]} field="humbleBundle" activeFilter={null} onTagClick={vi.fn()} onClearFilter={vi.fn()} />
    )
    expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument()
  })

  it("does not render an All button when onClearFilter is absent", () => {
    render(
      <FilterBar label="AI tags" tags={["Python"]} field="ai_tags" activeFilter={null} onTagClick={vi.fn()} />
    )
    expect(screen.queryByRole("button", { name: "All" })).not.toBeInTheDocument()
  })

  it("marks the matching tag button as active", () => {
    const activeFilter: ActiveFilter = { tag: "Python", field: "ai_tags" }
    render(
      <FilterBar label="AI tags" tags={["Python", "Databases"]} field="ai_tags" activeFilter={activeFilter} onTagClick={vi.fn()} />
    )
    // active button gets the dark filled style; inactive gets the plain border style
    const activeBtn = screen.getByRole("button", { name: "Python" })
    const inactiveBtn = screen.getByRole("button", { name: "Databases" })
    expect(activeBtn.className).toContain("bg-gray-900")
    expect(inactiveBtn.className).not.toContain("bg-gray-900")
  })

  it("calls onTagClick with tag and field when a tag button is clicked", async () => {
    const user = userEvent.setup()
    const onTagClick = vi.fn()
    render(
      <FilterBar label="AI tags" tags={["Python"]} field="ai_tags" activeFilter={null} onTagClick={onTagClick} />
    )
    await user.click(screen.getByRole("button", { name: "Python" }))
    expect(onTagClick).toHaveBeenCalledWith("Python", "ai_tags")
  })

  it("renders nothing when tags is empty", () => {
    const { container } = render(
      <FilterBar label="AI tags" tags={[]} field="ai_tags" activeFilter={null} onTagClick={vi.fn()} />
    )
    expect(container).toBeEmptyDOMElement()
  })

  it("applies the CSS hidden class when hidden=true, even with no tags", () => {
    const { container } = render(
      <FilterBar label="Topics" tags={[]} field="tags" activeFilter={null} onTagClick={vi.fn()} hidden />
    )
    expect(container.firstChild).toHaveClass("hidden")
  })
})

describe("FilterBarList", () => {
  it("renders the AI tags bar when ai tags are present", () => {
    render(
      <FilterBarList
        allTags={[]}
        allAiTags={["Python"]}
        allBundles={[]}
        activeFilter={null}
        onTagClick={vi.fn()}
        onClearFilter={vi.fn()}
      />
    )
    expect(screen.getByText("AI tags")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Python" })).toBeInTheDocument()
  })

  it("renders the Bundle bar when bundles are present", () => {
    render(
      <FilterBarList
        allTags={[]}
        allAiTags={[]}
        allBundles={["Pack A", "Pack B"]}
        activeFilter={null}
        onTagClick={vi.fn()}
        onClearFilter={vi.fn()}
      />
    )
    expect(screen.getByText("Bundle")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Pack A" })).toBeInTheDocument()
  })

  it("renders no visible bars when all tag lists are empty", () => {
    render(
      <FilterBarList
        allTags={[]}
        allAiTags={[]}
        allBundles={[]}
        activeFilter={null}
        onTagClick={vi.fn()}
        onClearFilter={vi.fn()}
      />
    )
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
  })
})
