import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"
import path from "path"

export default defineConfig({
  root: path.resolve(process.cwd()),
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    coverage: {
      provider: "v8",
      include: ["app/**/*.{ts,tsx}", "lib/**/*.{ts,tsx}", "scripts/**/*.ts"],
      exclude: [
        "**/*.test.*",
        "**/*.d.ts",
        // Next.js boilerplate — no meaningful logic to unit test
        "app/error.tsx",
        "app/layout.tsx",
        "app/page.tsx",
        "app/providers.tsx",
        // Real Redis client — throws at import without env vars
        "lib/redis.ts",
      ],
      reporter: ["text", "html"],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
})
