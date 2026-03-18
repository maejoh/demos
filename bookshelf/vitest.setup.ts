import "@testing-library/jest-dom"
import React from "react"
import { vi } from "vitest"

// next/image does server-side optimisation that doesn't work in jsdom —
// swap it out globally so any component test can render <Image> safely.
vi.mock("next/image", () => ({
  default: ({ src, alt }: { src: string; alt: string }) =>
    React.createElement("img", { src, alt }),
}))
