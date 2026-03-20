/**
 * Unit tests for ThemeToggle.
 *
 * Mocks next-themes so tests don't depend on ThemeProvider being mounted.
 * The component defers rendering until after mount (hydration guard), so
 * effects must flush before assertions.
 *
 * Uses resolvedTheme (not theme) so the button reflects the actual applied
 * theme — system preference is resolved to "dark" or "light" before render.
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { ThemeToggle } from "@/app/components/ThemeToggle"

const mockSetTheme = vi.fn()

vi.mock("next-themes", () => ({
  useTheme: vi.fn(),
}))

import { useTheme } from "next-themes"
const mockUseTheme = vi.mocked(useTheme)

describe("ThemeToggle", () => {
  it("renders the toggle button after mount", async () => {
    mockUseTheme.mockReturnValue({ resolvedTheme: "dark", setTheme: mockSetTheme } as any)
    render(<ThemeToggle />)
    await waitFor(() => expect(screen.getByRole("button")).toBeInTheDocument())
  })

  it("switches to light when clicked in dark mode", async () => {
    mockUseTheme.mockReturnValue({ resolvedTheme: "dark", setTheme: mockSetTheme } as any)
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await waitFor(() => screen.getByRole("button"))

    await user.click(screen.getByRole("button"))
    expect(mockSetTheme).toHaveBeenCalledWith("light")
  })

  it("switches to dark when clicked in light mode", async () => {
    mockUseTheme.mockReturnValue({ resolvedTheme: "light", setTheme: mockSetTheme } as any)
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await waitFor(() => screen.getByRole("button"))

    await user.click(screen.getByRole("button"))
    expect(mockSetTheme).toHaveBeenCalledWith("dark")
  })
})
