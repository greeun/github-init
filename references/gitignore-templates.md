# .gitignore Templates Reference

Detailed templates per project type. The `github_init.py` script embeds these; this file is the
readable reference for what gets written and why.

## How a template is shaped

A template is a list of `(section comment, [patterns])` pairs rather than a flat list. Sections
keep related patterns adjacent, and that adjacency is load-bearing: git resolves `!` exceptions by
last-match-wins, so `!.env*.example` only keeps working while it sits *after* `.env*`. Grouping
them lets the merge step move a section as one unit instead of stranding an exception above the
rule it is meant to override.

The generated file is assembled from three parts, in this order:

1. the project-type template below
2. the stray-lockfile section, for Node projects where the package manager is unambiguous
3. the shared agent-tooling block, which every project type receives

## Per-type templates

These are shown without the shared agent block, which is listed once further down.

### Node.js

```gitignore
# dependencies
node_modules/

# build output
dist/
build/
.next/
out/
*.tsbuildinfo

# logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
logs/

# test output
coverage/
.nyc_output/

# caches
.cache/
.turbo/
.eslintcache

# env files (example and template files stay tracked)
.env*
!.env*.example
!.env*.template

# editors
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

### Python

```gitignore
# byte-compiled
__pycache__/
*.py[cod]
*$py.class

# virtualenvs
.venv/
venv/

# build output
build/
dist/
*.egg-info/
*.egg

# test output
.pytest_cache/
.coverage
htmlcov/
.tox/

# notebooks
.ipynb_checkpoints/

# caches
.mypy_cache/
.ruff_cache/

# env files (example and template files stay tracked)
.env*
!.env*.example
!.env*.template

# editors
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

### Go

```gitignore
# binaries
*.exe
*.exe~
*.dll
*.so
*.dylib

# test output
*.test
*.out

# modules
vendor/
go.work
go.work.sum

# env files (example and template files stay tracked)
.env*
!.env*.example
!.env*.template

# editors
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

### Rust

```gitignore
# build output
/target/
**/*.rs.bk

# env files (example and template files stay tracked)
.env*
!.env*.example
!.env*.template

# editors
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

### Java

```gitignore
# build output
target/
build/
.gradle/
*.class
*.jar
*.war

# editors
.idea/
*.iml
.vscode/
*.swp
*.swo

# env files (example and template files stay tracked)
.env*
!.env*.example
!.env*.template

# OS
.DS_Store
Thumbs.db
```

### Ruby

```gitignore
# dependencies
vendor/bundle/
.bundle/

# build output
*.gem
*.rbc

# test output
coverage/
spec/reports/

# env files (example and template files stay tracked)
.env*
!.env*.example
!.env*.template

# editors
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

### General (fallback)

```gitignore
# logs
*.log
logs/

# temporary files
*.tmp
*.temp

# env files (example and template files stay tracked)
.env*
!.env*.example
!.env*.template

# editors
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

## Shared agent-tooling block

Appended to every project type. None of it describes the project, and some of it (`CLAUDE.md`,
MCP config) is personal enough that committing it publishes how an individual works rather than
how the code works.

The patterns are deliberately narrower than a bare `.ast*` or `.axt*` prefix. `.ast*` would also
swallow Astro's `.astro/` cache directory, which is a real build artifact some projects want to
reason about separately.

```gitignore
# claude code (instructions, local settings, session worktrees, MCP config)
CLAUDE.md
.claude/
.claude.json
.claude.json.*
.claude-*.json

# superpowers (auto-installed working notes)
.superpowers/
docs/superpowers/

# axt local profile (including backups)
.axt/
.axt-*
.axt.*

# ast (agent session tracker) local state
.ast/
.ast-*
.ast.*
```

## Stray lockfiles (Node projects)

A committed lockfile tells everyone who installs next which package manager to use, so two of them
in one repository is a contradiction. When exactly one is present, it identifies the project's
package manager and the rest are strays worth ignoring:

| Lockfile | Package manager |
|----------|-----------------|
| `pnpm-lock.yaml` | pnpm |
| `yarn.lock` | yarn |
| `package-lock.json` | npm |
| `bun.lockb` | bun |

When zero or several lockfiles exist, the script cannot tell which one is authoritative, so it
ignores none of them and says so in a warning. Guessing here would ignore the file the project
actually depends on.

## Merge Strategy

When a `.gitignore` already exists, the script appends rather than rewrites -- the existing file
may encode decisions this script knows nothing about. Deduplication alone is not enough, though,
because order decides what a `!` line means:

1. Read existing patterns, ignoring comments and blank lines, and compare case-insensitively.
2. Append only the patterns that are missing, under an `# Added by github-init` header, grouped
   into the same sections as the template.
3. Append a section containing `!` exceptions **whole** as soon as any of its patterns is new.
   Appending only the missing half would strand the exception above the pattern it overrides.
4. Restate the exceptions already in the file at the end. Everything new lands below them, so
   without this an added `.env*` would silently cancel an existing `!.env.example`.

## Verifying against what git already tracks

Adding a pattern never untracks anything. A file that is already committed keeps being committed
while `.gitignore` claims it is out of the repository, and that contradiction is what bites later:
someone reads the ignore file, assumes the file is gone, and is surprised when their edit to it
lands in a diff.

After merging, the script runs `git ls-files --ignored --exclude-standard -c` on existing
repositories and adds a `!<path>` exception for every tracked file the new rules would match, then
reports what it did. Entries the index still holds but the working tree no longer has are left
alone -- those are pending deletions, and resurrecting them would undo a removal the author
started.
