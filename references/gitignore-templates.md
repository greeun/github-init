# .gitignore Templates Reference

Detailed templates per project type. The `github_init.py` script embeds a subset of these; this file serves as the full reference.

## Node.js

```gitignore
node_modules/
dist/
build/
.next/
out/
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
.env
.env.local
.env.*.local
coverage/
.nyc_output/
.cache/
.DS_Store
Thumbs.db
```

## Python

```gitignore
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
env/
.env
build/
dist/
*.egg-info/
*.egg
.pytest_cache/
.coverage
htmlcov/
.tox/
.ipynb_checkpoints/
.DS_Store
Thumbs.db
```

## Go

```gitignore
*.exe
*.exe~
*.dll
*.so
*.dylib
*.test
*.out
vendor/
go.work
.DS_Store
Thumbs.db
```

## Rust

```gitignore
/target/
**/*.rs.bk
.DS_Store
Thumbs.db
```

## Java

```gitignore
target/
build/
.gradle/
*.class
*.jar
*.war
.idea/
*.iml
.DS_Store
Thumbs.db
```

## Ruby

```gitignore
vendor/bundle/
.bundle/
*.gem
*.rbc
coverage/
spec/reports/
.DS_Store
Thumbs.db
```

## General (fallback)

```gitignore
.DS_Store
Thumbs.db
.env
.env.local
*.log
logs/
*.tmp
*.temp
.vscode/
.idea/
*.swp
*.swo
```

## Merge Strategy

When a `.gitignore` already exists, the script performs a **smart merge**:

1. Read existing entries (ignore comments and blank lines for dedup)
2. Compare new entries case-insensitively
3. Append only unique new entries under `# Added by github-init` header
4. Preserve all original content and formatting
