# demos — Pre-Landing Review Checklist

## Critical (block ship)

### Secrets & Security
- DO flag: hardcoded API keys, tokens, or credentials in the diff
- DO flag: `.env` or `.env.local` files added or modified in the diff
- DO flag: sensitive values in `scripts/book_details.json` or similar data files committed to the repo

### Build integrity
- DO flag: TypeScript errors that would cause `tsc --noEmit` to fail
- DO flag: imports referencing modules that don't exist in the diff
- DO flag: broken Next.js API route handlers (missing default export or wrong handler signature)
- DO flag: `next.config.ts` changes that could break the Vercel build

### Portfolio criteria
- DO flag: hardcoded `localhost` URLs or ports in code that will be deployed to Vercel
- DO flag: demo pages that require user authentication to view (demos must be publicly accessible)
- DO flag: missing `README.md` in a newly added demo subfolder

## Informational (note, do not block)

### Code quality
- Note: unused imports or variables added in the diff
- Note: `console.log` statements left in production code paths (not scripts/)
- Note: TODO comments added in code without a corresponding TODOS.md entry
- Note: magic strings or numbers that could be named constants

### Portfolio completeness
- Note: new demo subfolder added without a `CLAUDE.md` documenting the stack and env vars
- Note: new demo not referenced in the root `README.md`
- Note: new environment variables used in code but not documented in the demo's `CLAUDE.md`
- Note: new Vercel environment variable required but not noted anywhere

### Next.js specifics
- Note: missing `loading.tsx` or `error.tsx` for newly added app routes that fetch data
- Note: large images added without using `next/image` optimization
- Note: `"use client"` added to a component that has no client-side interactivity (could be a server component)
- Note: new dynamic routes missing `generateStaticParams` where static generation would be appropriate

### Redis / data layer
- Note: new Redis key patterns not following the `{env}:{resource}:{id}` namespace convention
- Note: Redis reads without a fallback for missing/null values

## DO NOT flag
- `package-lock.json` changes (normal dependency lockfile updates)
- `public/covers/` image additions (expected output from the epub extraction pipeline)
- `scripts/book_list.json` changes (expected tracking file, not committed)
- `scripts/book_details.json` (not committed — in .gitignore)
- Pre-existing TypeScript strict mode warnings in files not touched by this diff
- Tailwind CSS class ordering (not enforced)
