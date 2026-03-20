import { describe, it, expect, vi, beforeEach } from "vitest"
import { castVote, removeVote } from "@/app/actions"
import { redis } from "@/lib/redis"

vi.mock("@/lib/redis", () => ({
  redis: {
    incr: vi.fn(),
    decr: vi.fn(),
  },
  key: (k: string) => `test:${k}`,
}))

describe("castVote", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("increments the vote key for the given isbn", async () => {
    vi.mocked(redis.incr).mockResolvedValue(1)
    await castVote("9781234567890")
    expect(redis.incr).toHaveBeenCalledWith("test:votes:9781234567890")
  })

  it("propagates Redis errors to the caller", async () => {
    vi.mocked(redis.incr).mockRejectedValue(new Error("connection refused"))
    await expect(castVote("9781234567890")).rejects.toThrow("connection refused")
  })
})

describe("removeVote", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("decrements the vote key for the given isbn", async () => {
    vi.mocked(redis.decr).mockResolvedValue(0)
    await removeVote("9781234567890")
    expect(redis.decr).toHaveBeenCalledWith("test:votes:9781234567890")
  })

  it("propagates Redis errors to the caller", async () => {
    vi.mocked(redis.decr).mockRejectedValue(new Error("connection refused"))
    await expect(removeVote("9781234567890")).rejects.toThrow("connection refused")
  })
})
