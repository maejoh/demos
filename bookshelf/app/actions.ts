"use server"

import { redis, key } from "@/lib/redis"

export async function castVote(isbn: string): Promise<void> {
  await redis.incr(key(`votes:${isbn}`))
}

export async function removeVote(isbn: string): Promise<void> {
  await redis.decr(key(`votes:${isbn}`))
}
