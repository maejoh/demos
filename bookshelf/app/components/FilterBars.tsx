"use client"

export type FilterField = "tags" | "ai_tags" | "humbleBundle"
export type ActiveFilter = { tag: string; field: FilterField } | null

type TagButtonProps = {
  children: React.ReactNode
  active: boolean
  onClick: () => void
}

export function CategoryFilterButton({ children, active, onClick }: TagButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`text-sm px-3 py-1 rounded-full border transition-colors ${
        active
          ? "border-gray-900 bg-gray-900 text-white dark:border-white dark:bg-white dark:text-gray-900"
          : "border-gray-200 dark:border-gray-800 hover:border-gray-400 dark:hover:border-gray-600"
      }`}
    >
      {children}
    </button>
  )
}

type FilterBarProps = {
  label: string
  tags: string[]
  field: FilterField
  activeFilter: ActiveFilter
  onTagClick: (tag: string, field: FilterField) => void
  onClearFilter?: () => void
  hidden?: boolean
}

export function FilterBar({ label, tags, field, activeFilter, onTagClick, onClearFilter, hidden }: FilterBarProps) {
  if (!hidden && tags.length === 0) return null
  return (
    <div className={`${hidden ? "hidden" : "flex"} flex-wrap gap-2 items-center`}>
      <span className="text-xs text-gray-400 dark:text-gray-500 w-12 shrink-0">{label}</span>
      {onClearFilter && tags.length > 0 && (
        <CategoryFilterButton active={activeFilter === null} onClick={onClearFilter}>
          All
        </CategoryFilterButton>
      )}
      {tags.map((tag) => (
        <CategoryFilterButton
          key={tag}
          active={activeFilter?.tag === tag && activeFilter?.field === field}
          onClick={() => onTagClick(tag, field)}
        >
          {tag}
        </CategoryFilterButton>
      ))}
    </div>
  )
}

type FilterBarListProps = {
  allTags: string[]
  allAiTags: string[]
  allBundles: string[]
  activeFilter: ActiveFilter
  onTagClick: (tag: string, field: FilterField) => void
  onClearFilter: () => void
}

export function FilterBarList({ allTags, allAiTags, allBundles, activeFilter, onTagClick, onClearFilter }: FilterBarListProps) {
  return (
    <div className="space-y-3 mb-8">
      <FilterBar label="Topics" tags={allTags} field="tags" activeFilter={activeFilter} onTagClick={onTagClick} onClearFilter={onClearFilter} hidden />
      <FilterBar label="AI tags" tags={allAiTags} field="ai_tags" activeFilter={activeFilter} onTagClick={onTagClick} onClearFilter={onClearFilter} />
      <FilterBar label="Bundle" tags={allBundles} field="humbleBundle" activeFilter={activeFilter} onTagClick={onTagClick} onClearFilter={onClearFilter} />
    </div>
  )
}
