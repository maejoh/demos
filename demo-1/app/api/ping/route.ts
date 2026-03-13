import { redis } from "@/lib/redis"

export async function GET() {
  await redis.set("ping", "pong")
  const value = await redis.get("ping")
  return Response.json({ value })
}
