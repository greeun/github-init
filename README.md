# github-init

Claude Code skill that automates GitHub repository initialization.

Git init, `.gitignore` generation, GitHub repo creation, and push -- all in one command.

## Features

- **Project type auto-detection** -- Node.js, Python, Go, Rust, Java, Ruby (6 types)
- **Smart `.gitignore`** -- auto-generates from templates, merges with existing files
- **Sensitive file protection** -- detects `.env`, `*.pem`, `*.key` and adds to `.gitignore`
- **Edge case handling** -- existing `.git/`, existing remote, existing commits
- **Dry-run mode** -- preview all steps before executing
- **Private by default** -- safe default visibility

## Prerequisites

```bash
# git
git --version

# GitHub CLI (authenticated)
brew install gh   # macOS
gh auth login
```

## Installation

Symlink the skill into Claude Code's skill directory:

```bash
ln -s /path/to/github-init ~/.claude/skills/github-init
```

## Usage

### In Claude Code (natural language)

Just ask Claude:

```
"깃허브에 올려줘"
"initialize this as a GitHub repo"
"push to GitHub as private"
"깃허브 저장소 생성해줘"
```

Claude will:
1. Detect the project type
2. Ask for repo name, visibility, description
3. Run the initialization
4. Report the result

### CLI (direct script usage)

**Detect project info:**

```bash
python3 scripts/github_init.py detect
```

```json
{
  "suggested_repo_name": "my-project",
  "project_type": "nodejs",
  "has_git": false,
  "has_remote": false,
  "has_gitignore": false,
  "sensitive_files": [".env"]
}
```

**Initialize (private, default):**

```bash
python3 scripts/github_init.py init --name my-repo
```

**Initialize (public, with description):**

```bash
python3 scripts/github_init.py init \
  --name my-repo \
  --visibility public \
  --description "My awesome project"
```

**Preview without changes:**

```bash
python3 scripts/github_init.py init --name my-repo --dry-run
```

**Skip `.gitignore` generation:**

```bash
python3 scripts/github_init.py init --name my-repo --skip-gitignore
```

### CLI Options

| Subcommand | Flag | Description |
|------------|------|-------------|
| `detect` | `[path]` | Target directory (default: `.`) |
| `init` | `--name` | Repository name (default: directory name) |
| | `--visibility` | `public` or `private` (default: `private`) |
| | `--description` | Repository description |
| | `--skip-gitignore` | Don't generate/merge `.gitignore` |
| | `--dry-run` | Preview mode, no changes made |

## How It Works

```
detect project type
       |
   has .git? ---no---> git init
       |
 has .gitignore? ---no---> generate from template
       |            |
       |           yes---> smart merge (deduplicate + append)
       |
 has commits? ---no---> git add . && git commit
       |
 has remote? ---no---> gh repo create --push
       |
     done
```

### Supported Project Types

| Type | Detected by |
|------|-------------|
| Node.js | `package.json`, `yarn.lock`, `pnpm-lock.yaml` |
| Python | `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile` |
| Go | `go.mod`, `go.sum` |
| Rust | `Cargo.toml`, `Cargo.lock` |
| Java | `pom.xml`, `build.gradle` |
| Ruby | `Gemfile`, `Gemfile.lock` |
| General | Fallback when no markers found |

### Smart `.gitignore` Merge

When a `.gitignore` already exists, the script:
1. Reads existing entries
2. Compares new template entries (case-insensitive)
3. Appends only unique entries under `# Added by github-init`
4. Preserves all original content

## File Structure

```
github-init/
├── SKILL.md                # Skill definition for Claude Code
├── README.md               # This file
├── scripts/
│   └── github_init.py      # Main automation script
└── references/
    └── gitignore-templates.md  # Full .gitignore template reference
```

## Troubleshooting

**`gh: command not found`**
```bash
brew install gh    # macOS
sudo apt install gh  # Ubuntu/Debian
```

**`gh not authenticated`**
```bash
gh auth login
```

**`Repository already exists`**
Use a different name or link manually:
```bash
git remote add origin https://github.com/USER/REPO.git
git push -u origin main
```

**Branch mismatch (main vs master)**
The script defaults to `main`. If your project already uses `master`, the existing branch name is preserved.

## License

MIT
