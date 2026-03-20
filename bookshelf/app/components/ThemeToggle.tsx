"use client"

import { useTheme } from "next-themes"
import { useEffect, useState } from "react"

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  // Only render after mount — avoids hydration mismatch since server
  // doesn't know the user's theme preference.
  useEffect(() => setMounted(true), [])
  if (!mounted) return null

  const isDark = resolvedTheme === "dark"

  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      className="w-9 h-9 flex items-center justify-center rounded-full border border-gray-900 dark:border-gray-100 bg-gray-900 dark:bg-gray-100 text-gray-100 dark:text-gray-900 hover:bg-gray-700 dark:hover:bg-gray-300 hover:scale-110 transition-all text-sm"
    >
      {isDark ? "☀︎" : "☽"}
    </button>
  )
}
