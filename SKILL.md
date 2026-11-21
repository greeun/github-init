---
name: github-init
description: |
  Initialize local git repository and create GitHub remote repository with initial commit and push.
  Automates project detection, .gitignore generation, and edge case handling.
  Also updates the .gitignore of an existing repository on its own, without creating a remote.
  Use when: "initialize git repo", "create GitHub repository", "push to GitHub", "set up git",
  "update .gitignore", "깃허브 초기화", "깃 설정", "저장소 생성", "깃허브 연동", "깃허브 푸시",
  "깃허브에 올려줘", ".gitignore 업데이트", ".gitignore 갱신", ".gitignore 정리".
version: 1.3.0
---

# GitHub Repository Initialization

Automates git init, .gitignore generation, GitHub repo creation, and push as one workflow.
The .gitignore step can also run alone; see [Updating .gitignore only](#updating-gitignore-only).

## Prerequisites

- `git` installed
- `gh` CLI installed and authenticated (`gh auth login`); not needed for the `gitignore` subcommand

## Output Language

Everything this skill writes into the repository or onto GitHub is in English, whatever language
the conversation happens to be in. A repository is read by people who were never part of that
conversation, so what it contains has to stand on its own.

| Output | Rule |
|--------|------|
| Repository name | ASCII lowercase kebab-case, e.g. `order-sync-api` |
| Description | One English sentence, no trailing period, roughly ten words |
| Commit message | English; the script writes `Initial commit` |
| `.gitignore` comments | English; written by the script |
| Any document written into the repository | English, e.g. README, LICENSE, CONTRIBUTING, docs |

Whole documents follow the same rule, not just these short values. When the initialization also
produces files, whether a README, a LICENSE, a CONTRIBUTING guide or anything else the user asks
for while setting the repository up, write them in English as well. A repository whose metadata is
English while its README is not still forces the next reader to switch languages halfway through.

Talking to the user is the exception. AskUserQuestion prompts, warnings and the Phase 4 report
follow whatever language the user is using. Only what ends up inside the repository is fixed to
English.

Two rules decide what you write:

- **An explicit input wins.** When the user hands you a name or a description in another
  language, pass it through unchanged instead of translating it. The same holds when they ask for
  a document in a particular language: write it the way they asked.
- **When the value is yours to draft, translate the meaning rather than the sound.** A directory
  named `주문 동기화 API` becomes `order-sync-api`, never `jumun-donggihwa-api`. This applies to
  `suggested_repo_name` as well, since it is only the directory name: normalize it to ASCII
  kebab-case before offering it, and say what you derived it from when the original was not ASCII.

## Workflow

### Phase 1: Detect Project

Detect the project type and git status automatically.

```bash
python3 ~/.claude/skills/github-init/scripts/github_init.py detect
```

Example output:
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
| Repository name | `suggested_repo_name` from detect, normalized to ASCII kebab-case | Free text |
| Visibility | private | public, private |
| Description | An English one-liner drafted from the detected project type and contents | Free text |

Draft the description instead of leaving it empty. A draft is easy for the user to overwrite,
while an empty description is easy to forget and harder to notice later.

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

**`.gitignore` lands before the first push, always.** Once a file reaches the remote it stays in
the history even if a later commit ignores it, so the merged `.gitignore` has to be committed on
every branch you push before `gh repo create` or `git push` runs. `init` keeps this order on its
own: it merges `.gitignore`, commits, then creates the remote and pushes.

When the repository already has commits (`has_commits: true` from detect), do not run `init`,
because it would commit every pending change as `Initial commit` on the current branch. Run the
steps by hand, in this order, and do not reorder them to save time:

1. Update `.gitignore` with the `gitignore` subcommand, following
   [Updating .gitignore only](#updating-gitignore-only), and commit it where the repository's
   rules say work lands (a branch or worktree when they ask for one).
2. Bring that commit into every branch you are about to push. If merging needs the user's
   approval under the repository's rules, ask now and wait; creating the remote is not a reason
   to skip that approval.
3. Check what will leave the machine: `git ls-files` on each branch to push should contain no
   secret file, and `git log --all --diff-filter=A --name-only --format=` should show none
   added in earlier commits either. If one appears, stop and tell the user before pushing.
4. Only then create the remote and push:
   `gh repo create <name> --private --description "<text>"`, `git remote add origin <url>`,
   and `git push -u origin <branch>` for each branch the user chose.

If the user asks to push before the `.gitignore` merge is approved, say that the current rules
will apply to what gets pushed, show which secret files those rules already cover, and push only
on their confirmation.

### Phase 4: Report Result

Show the user:
- Created repository URL
- .gitignore entries added
- Branch name
- Any warnings (sensitive files detected, lockfiles left alone, exceptions added for tracked files)
- The English name or description you drafted, whenever it differs from what the user said, so
  they can correct it while the repository is still new

## Updating .gitignore only

Use the `gitignore` subcommand when the user asks to update, refresh or tidy `.gitignore`, and
when an existing repository needs the merge without the rest of `init`. It applies the same
templates and merge rules as `init`, then stops: it needs no `gh`, and it never stages, commits,
creates a remote or pushes.

Prefer it over `init` on any repository that already has commits. On such a repository `init`
runs `git add .` and commits everything under the message `Initial commit`, which sweeps
unrelated changes into a commit with a misleading message. Likewise, when `init` stops because
the repository name is taken on GitHub, run this subcommand for the `.gitignore` part and settle
the remote separately with the user.

1. **Pick where the change lands.** Follow the repository's own rules. If its instructions say
   work happens on a branch or in a worktree, create that first and run the command there, not
   in the main working tree. Never leave the change uncommitted on a shared branch.
2. **Preview.** `python3 ~/.claude/skills/github-init/scripts/github_init.py gitignore --dry-run`
   prints every pattern it would append. Read the list against the project: a pattern for a file
   or directory the project deliberately keeps (generated code that is committed, a tracked
   config folder) has to be raised with the user before applying.
3. **Apply.** Run the same command without `--dry-run`, then read `git diff .gitignore`.
4. **Verify.** Confirm both directions:
   - `git ls-files --ignored --exclude-standard -c` prints nothing, or only the paths the script
     reported in its warning with a `!<path>` exception.
   - `git check-ignore -v --no-index <file>` on a real secret file (such as `.env.local`) shows an
     ignoring rule, and on a tracked example file (such as `.env.example`) shows a `!` rule.
5. **Report, then commit only on request.** Tell the user which patterns were added, which were
   left out because they name tracked files, and any warning. Commit when the user asks, in the
   repository's own commit-message convention, and merge only the way its instructions allow.
   A request to create the remote or push counts as a request to commit: the `.gitignore` commit
   is the first step of that flow (see Phase 3).

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

**A literal that names a tracked file is not written.** Template entries such as `CLAUDE.md` are
there because most projects do not keep that file. When the repository already tracks it, the
author decided otherwise, and writing the pattern followed by a `!CLAUDE.md` exception would only
leave two lines that contradict each other. Such literals are dropped before merging, and the
script says which ones it left out. Globs and directory patterns are not dropped; they go through
the exception check above instead.

Every project type also receives a shared block for agent tooling (`CLAUDE.md`, `.claude/`,
`.superpowers/`, `.axt*`, `.ast*`) since in most projects none of it describes the project. See
`references/gitignore-templates.md` for the full templates and the merge rules.

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Already has `.git/` | Skip `git init`, proceed to remote |
| Already has remote | Show existing URL, skip `gh repo create` |
| Has existing `.gitignore` | Smart merge: append missing entries, keep `!` exceptions working |
| Has existing commits | Don't run `init`; update and merge `.gitignore` first, then create the remote and push (see Phase 3) |
| Repo name taken on GitHub | Error with suggestion to use different `--name` |
| Sensitive files found (.env) | Auto-add to .gitignore before commit |
| Tracked file matches a new rule | Add `!<path>` exception so it stays tracked, and warn |
| Template literal names a tracked file (e.g. `CLAUDE.md`) | Leave the pattern out and report it |
| Only `.gitignore` needs updating | Use the `gitignore` subcommand; nothing is committed |
| Several lockfiles present | Ignore none of them, warn that the package manager is ambiguous |
| Lockfile deleted but still in index | Treated as a pending deletion, no exception added |
| Non-ASCII directory name | Offer an English kebab-case name and say what it was derived from |

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
| `gitignore [path]` | Create or merge `.gitignore` only; no commit, no remote. Takes `--dry-run` |

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
