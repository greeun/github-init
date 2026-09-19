---
name: github-init
description: |
  Initialize local git repository and create GitHub remote repository with initial commit and push.
  Automates project detection, .gitignore generation, and edge case handling.
  Use when: "initialize git repo", "create GitHub repository", "push to GitHub", "set up git",
  "깃허브 초기화", "깃 설정", "저장소 생성", "깃허브 연동", "깃허브 푸시", "깃허브에 올려줘".
version: 1.1.0
---

# GitHub Repository Initialization

Git init, .gitignore 생성, GitHub repo 생성, push를 한 워크플로우로 자동화.

## Prerequisites

- `git` installed
- `gh` CLI installed and authenticated (`gh auth login`)

## Workflow

### Phase 1: Detect Project

프로젝트 타입과 git 상태를 자동 감지한다.

```bash
python3 ~/.claude/skills/github-init/scripts/github_init.py detect
```

출력 예시:
```json
{
  "suggested_repo_name": "my-project",
  "project_type": "nodejs",
  "detected_files": ["package.json", "node_modules"],
  "has_git": false,
  "has_remote": false,
  "has_gitignore": false,
  "package_manager": "pnpm",
  "lockfile": "pnpm-lock.yaml",
  "stray_lockfiles": ["yarn.lock", "package-lock.json", "bun.lockb"],
  "sensitive_files": [".env"],
  "tracked_but_ignored": []
}
```

`package_manager` is `null` when zero or several lockfiles are present — the script will not guess
which one is authoritative. `tracked_but_ignored` lists files git already tracks that the current
ignore rules also match; it is empty until a repository exists.

### Phase 2: Ask User Preferences

Use **AskUserQuestion** to gather:

| Question | Default | Options |
|----------|---------|---------|
| Repository name | `suggested_repo_name` from detect | Free text |
| Visibility | private | public, private |
| Description | (none) | Free text |

### Phase 3: Execute

Run the init script with gathered inputs:

```bash
python3 ~/.claude/skills/github-init/scripts/github_init.py init \
  --name "my-repo" \
  --visibility private \
  --description "My project"
```

Add `--dry-run` to preview without making changes.
Add `--skip-gitignore` to keep existing .gitignore as-is.

### Phase 4: Report Result

Show the user:
- Created repository URL
- .gitignore entries added
- Branch name
- Any warnings (sensitive files detected, lockfiles left alone, exceptions added for tracked files)

## How .gitignore is generated

Three things make the generated file differ from a plain template dump. Each exists because the
naive version quietly does the wrong thing.

**Order matters for `!` exceptions.** Git resolves them by last-match-wins, so `!.env*.example`
only works while it sits after `.env*`. Templates are therefore grouped into sections, and a
section carrying exceptions is appended as a unit. When merging into an existing file, any `!`
lines already there are restated at the end — otherwise a newly appended `.env*` would silently
cancel the author's existing `!.env.example`.

**One lockfile identifies the package manager.** A committed lockfile tells everyone who installs
next which tool to use, so two of them contradict each other. When exactly one is present, the
others are ignored as strays. When zero or several are present, none are touched and the script
warns instead — guessing would ignore the file the project actually depends on.

**Adding a pattern never untracks a file.** On an existing repository the script checks
`git ls-files --ignored --exclude-standard -c` after merging, and adds a `!<path>` exception for
every tracked file the new rules would have shadowed. Without this the ignore file would claim
those files are gone while git keeps committing them. Files the index still holds but the working
tree no longer has are left alone: those are pending deletions, not conflicts.

Every project type also receives a shared block for agent tooling (`CLAUDE.md`, `.claude/`,
`.superpowers/`, `.axt*`, `.ast*`) since none of it describes the project. See
`references/gitignore-templates.md` for the full templates and the merge rules.

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Already has `.git/` | Skip `git init`, proceed to remote |
| Already has remote | Show existing URL, skip `gh repo create` |
| Has existing `.gitignore` | Smart merge: append missing entries, keep `!` exceptions working |
| Has existing commits | Skip initial commit, push existing |
| Repo name taken on GitHub | Error with suggestion to use different `--name` |
| Sensitive files found (.env) | Auto-add to .gitignore before commit |
| Tracked file matches a new rule | Add `!<path>` exception so it stays tracked, and warn |
| Several lockfiles present | Ignore none of them, warn that the package manager is ambiguous |
| Lockfile deleted but still in index | Treated as a pending deletion, no exception added |

## Supported Project Types

Auto-detected from marker files:

| Type | Markers |
|------|---------|
| Node.js | `package.json`, `yarn.lock`, `pnpm-lock.yaml` |
| Python | `requirements.txt`, `pyproject.toml`, `setup.py` |
| Go | `go.mod`, `go.sum` |
| Rust | `Cargo.toml` |
| Java | `pom.xml`, `build.gradle` |
| Ruby | `Gemfile` |
| General | Fallback if nothing detected |

See `references/gitignore-templates.md` for full template details.

## Script Reference

### `scripts/github_init.py`

| Subcommand | Description |
|------------|-------------|
| `detect [path]` | Detect project type and git status (JSON) |
| `init` | Full initialization workflow |

**init options:**

| Flag | Description |
|------|-------------|
| `--name NAME` | Repository name (default: directory name) |
| `--visibility {public,private}` | Repo visibility (default: private) |
| `--description TEXT` | Repository description |
| `--skip-gitignore` | Don't generate/merge .gitignore |
| `--dry-run` | Preview mode, no changes |

## Troubleshooting

**"gh not authenticated"**: Run `gh auth login` and follow prompts.

**"Repository already exists"**: Use `--name different-name` or manually add remote:
```bash
git remote add origin https://github.com/USER/REPO.git
git push -u origin main
```

**Branch mismatch**: The script defaults to `main`. If your repo uses `master`, the script respects the existing branch name.
