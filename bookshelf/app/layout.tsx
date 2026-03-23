import type { Metadata } from "next"
import { Geist } from "next/font/google"
import { Providers } from "./providers"
import "./globals.css"
import { Analytics } from "@vercel/analytics/next"

const geist = Geist({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "Technical Library",
  description: "Books I own, am reading, or have read — searchable by topic.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={geist.className}>
        <Providers>
          {children}
        </Providers>
        <Analytics />
      </body>
    </html>
  )
}
