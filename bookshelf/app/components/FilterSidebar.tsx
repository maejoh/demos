"use client"

export type FilterField = "ai_tags" | "humbleBundle"
export type ActiveFilters = Partial<Record<FilterField, string[]>>

type FilterSectionProps = {
  label: string
  tags: string[]
  field: FilterField
  activeFilters: ActiveFilters
  onToggle: (tag: string, field: FilterField) => void
}

function FilterSection({ label, tags, field, activeFilters, onToggle }: FilterSectionProps) {
  if (tags.length === 0) return null
  const selected = activeFilters[field] ?? []
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-2">
        {label}
      </p>
      <ul className="space-y-1.5">
        {tags.map((tag) => (
          <li key={tag}>
            <label className="flex items-center gap-2 cursor-pointer group">
              <input
                type="checkbox"
                checked={selected.includes(tag)}
                onChange={() => onToggle(tag, field)}
                className="h-4 w-4 rounded accent-gray-900 dark:accent-white"
              />
              <span className="text-sm text-gray-600 dark:text-gray-400 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">
                {tag}
              </span>
            </label>
          </li>
        ))}
      </ul>
    </div>
  )
}

type FilterSidebarProps = {
  allAiTags: string[]
  allBundles: string[]
  activeFilters: ActiveFilters
  onToggle: (tag: string, field: FilterField) => void
  onClearAll: () => void
  isOpen: boolean
  onToggleSidebar: () => void
}

export function FilterSidebar({
  allAiTags,
  allBundles,
  activeFilters,
  onToggle,
  onClearAll,
  isOpen,
  onToggleSidebar,
}: FilterSidebarProps) {
  const activeCount = Object.values(activeFilters).reduce(
    (sum, tags) => sum + tags.length, // tags is guaranteed to be string[]
    0
  )

  return (
    <div className="md:w-52 shrink-0 md:sticky md:top-8">
      {/* Mobile toggle — hidden on desktop */}
      <button
        className="md:hidden w-full flex items-center justify-between px-3 py-2 mb-3 rounded-lg border border-gray-200 dark:border-gray-800 text-sm font-medium"
        onClick={onToggleSidebar}
      >
        <span>Filters{activeCount > 0 ? ` · ${activeCount}` : ""}</span>
        <span className="text-gray-400 text-xs">{isOpen ? "▲" : "▼"}</span>
      </button>

      {/* Sidebar content — hidden on mobile unless open, always shown on desktop */}
      <div className={`${isOpen ? "block" : "hidden"} md:block space-y-6`}>
        {activeCount > 0 && (
          <button
            onClick={onClearAll}
            className="text-xs text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 underline transition-colors"
          >
            Clear all
          </button>
        )}
        <FilterSection
          label="AI Tags"
          tags={allAiTags}
          field="ai_tags"
          activeFilters={activeFilters}
          onToggle={onToggle}
        />
        <FilterSection
          label="Humble Bundle Collection"
          tags={allBundles}
          field="humbleBundle"
          activeFilters={activeFilters}
          onToggle={onToggle}
        />
      </div>
    </div>
  )
}
