# demos — portfolio repo

## Purpose
A portfolio of deployed demos targeting AI companies. Each demo should be live, linkable, and self-explanatory.

## Deployment
- Host: Vercel
- Each demo lives in its own subfolder (`demo-1/`, `demo-2/`, etc.)
- Milestones are "deployed and linkable", moving from simple but complete React/typesript projects to more advanced demos with MCP and Anthropic API calls.


## Structure
```
demos/
  demo-1/   — BookShelf (Next.js + Redis + epub pipeline)
```

## Preferences
I usually use Claude in 'edit automatically' mode, but I prefer that edits only happen when I explicitly ask for them, and not just when Claude thinks there's a clear answer to my question and assumes that implementing it is what I want it to do next. If I ask a question, answer the question, don't modify the code base yet.