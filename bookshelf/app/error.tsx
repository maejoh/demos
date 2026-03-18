"use client"

export default function Error() {
  return (
    <div className="max-w-2xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-bold tracking-tight mb-2">Something went wrong</h1>
      <p className="text-gray-500 dark:text-gray-400">
        An unexpected error occurred. Try refreshing the page.
      </p>
    </div>
  )
}
