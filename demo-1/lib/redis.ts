import { Redis } from "@upstash/redis"

export const redis = Redis.fromEnv()

// VERCEL_ENV is set automatically by Vercel: "production", "preview", or "development".
// Locally it is undefined, so we fall back to "development".
const env = process.env.VERCEL_ENV ?? "development"

export const key = (k: string) => `${env}:${k}`
