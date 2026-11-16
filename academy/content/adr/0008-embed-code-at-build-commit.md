---
title: Lessons embed repository files at the build commit
status: Accepted
date: 2026-11-16
summary: Lessons embed repository files at the build commit.
---

## Context

Tutorial snippets copied by hand drift from the code they describe.

## Decision

Lesson Markdown uses `::: embed path "start pattern" ["end pattern"]`. The build reads the file from the repository, extracts the block (brace matching for JS, YANG, and JSON; indentation for Python), and links to GitHub at the exact commit with line numbers. A missing file or pattern fails the build. `repo:` links work the same way.

## Consequences

- Renaming a function without updating the lesson breaks CI, which is the point.
- `academy/dist` is never committed; it is rebuilt on every deploy.
