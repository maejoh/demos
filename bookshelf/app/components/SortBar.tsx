"use client"

export type SortField = "title" | "author" | "humbleBundle" | "votes"
export type SortDir = "asc" | "desc"

const SORT_OPTIONS: { field: SortField; label: string }[] = [
  { field: "title", label: "Title" },
  { field: "author", label: "Author" },
  { field: "humbleBundle", label: "Bundle" },
  { field: "votes", label: "Votes" },
]

type SortBarProps = {
  sortField: SortField
  sortDir: SortDir
  onSort: (field: SortField) => void
}

export function SortBar({ sortField, sortDir, onSort }: SortBarProps) {
  return (
    <div className="flex flex-wrap gap-2 items-center mb-6">
      <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0">Sort by</span>
      {SORT_OPTIONS.map(({ field, label }) => {
        const isActive = sortField === field
        return (
          <button
            key={field}
            onClick={() => onSort(field)}
            className={`text-sm px-3 py-1 rounded-full border transition-colors ${
              isActive
                ? "border-gray-900 bg-gray-900 text-white dark:border-white dark:bg-white dark:text-gray-900"
                : "border-gray-200 dark:border-gray-800 hover:border-gray-400 dark:hover:border-gray-600"
            }`}
          >
            {label}{isActive ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
          </button>
        )
      })}
    </div>
  )
}
