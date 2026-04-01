# demos

Welcome to my demos repo! At the moment, there is one main portfolio project where I 
organize and display a bunch of technical books, and where site visitors can provide 
feedback on which ones tackle skills they're actually interested in, adding to an 
aggregate vote count that reflects general interest.

See also: ([My portfolio website](https://maejoh.io/))

## BookShelf ([live demo](https://demos.maejoh.io/))

![BookShelf screenshot](./bookshelf/public/demo-screenshot.png)

### The Project

[Humble Bundle](https://www.humblebundle.com/) is a website that often offers "bundles"
of games, software, and books, on a myriad of topics. Bundles are often heavily 
discounted, and a portion of the proceeds go to a particular charity for each bundle.
As a lover of all books nonfiction, I've gotten most of their tech-related book bundles
over the last few years. However, many of the books are very topic-specific, and while
certain titles caught my attention from the get-go, many are as-of-yet unread. 

Most of my prior work in the industry has been proprietary, and was left behind with 
each job transition. Since I am back on the hunt for my next opportunity, I wanted to 
put together a public repo and live demo, and I figured a bookshelf app with a voting 
system would make a simple but interesting concept to build around - data ingestion, 
persistent storage, local state, responsive UI, sorting and filtering logic. All books 
in the app are actual books that I own, and all votes reflect real site visitors 
clicking on buttons over time.

The app demonstrates full-stack Next.js, Redis-backed data (Upstash), and a Python and 
TypeScript processing pipeline. Part of the pipeline also makes calls to the Google 
Books API, to get book descriptions and fill in missing metadata from the epubs, as 
well as the Anthropic API, to request an LLM to choose and assign topic tags for the 
library (referred to as AI tags).

For more technical details, please see the READMEs in the [./bookshelf](./bookshelf) directory. 

## What's built

- Browsable library with cover art, metadata, and per-book upvotes
- Redis data store, namespaced by environment (prod / dev / prev)
- Python epub pipeline: OPF extraction → Google Books API enrichment → Redis seed
- AI tagging via Anthropic API: two-pass vocabulary discovery + bulk assignment across the full library

## What's coming

- **LLM features** — book recommendations, job description matching, natural language queries
- **MCP server** — endpoints to enable querying the library and interacting with other LLM features from the UI, but programmatically 

---

## Development workflow

I spent my first 5 years in the industry coding without AI. I believe that has made an
enormous difference in my ability to effectively code **with** AI, and this project was vastly
expedited by use of Claude Code, generally from the CLI. I work in small steps so that all 
changes can be reviewed personally, and I frequently correct or redirect the AI when needed, or 
even just ask for more details and resources so I can properly evaluate what has been written. 
I still lean heavily on my past experience in similar (if larger) code bases, and have included
unit tests with coverage tools and sensible splitting of components and standalone logic. I keep 
the dev server running as I work, and run the unit tests and try out the UI manually as I go, 
making sure to follow the same good principles and practices I would if coding by hand.

In addition to Claude Code's built-in abilities, this repo also uses a customized subset of 
[garrytan/gstack](https://github.com/garrytan/gstack) skills for Claude Code. These modified skills 
are included in the repo for your viewing, if you like, and the customizations summarized below. 
I have personally found /plan-ceo-review and /plan-eng-review particularly helpful. 

| Skill | Source | Customized? |
|---|---|---|
| `/plan-ceo-review` | gstack v1.0.0 | Adapted for TypeScript/Next.js (removed Rails-specific sections) |
| `/plan-eng-review` | gstack v1.0.0 | Adapted for TypeScript/Next.js (removed Rails-specific sections) |
| `/review` | gstack v1.0.0 | Greptile integration removed; checklist path updated |
| `review/checklist.md` | — | **Written from scratch** |
