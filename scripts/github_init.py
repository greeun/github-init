#!/usr/bin/env python3
"""GitHub Repository Initialization Automation.

Subcommands:
    detect  - Detect project type, git status, suggest .gitignore (JSON output)
    init    - Full initialization: git init, .gitignore, commit, gh repo create, push

Usage:
    python3 github_init.py detect [path]
    python3 github_init.py init --name my-repo --visibility private
    python3 github_init.py init --name my-repo --visibility public --description "My project" --dry-run
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# .gitignore templates (embedded for zero-dependency execution)
# ---------------------------------------------------------------------------

GITIGNORE_TEMPLATES = {
    "nodejs": [
        "node_modules/", "dist/", "build/", ".next/", "out/",
        "*.log", "npm-debug.log*", "yarn-debug.log*", "yarn-error.log*",
        ".env", ".env.local", ".env.*.local",
        "coverage/", ".nyc_output/", ".cache/",
        ".DS_Store", "Thumbs.db",
    ],
    "python": [
        "__pycache__/", "*.py[cod]", "*$py.class",
        ".venv/", "venv/", "env/", ".env",
        "build/", "dist/", "*.egg-info/", "*.egg",
        ".pytest_cache/", ".coverage", "htmlcov/", ".tox/",
        ".ipynb_checkpoints/",
        ".DS_Store", "Thumbs.db",
    ],
    "go": [
        "*.exe", "*.exe~", "*.dll", "*.so", "*.dylib",
        "*.test", "*.out",
        "vendor/", "go.work",
        ".DS_Store", "Thumbs.db",
    ],
    "rust": [
        "/target/", "**/*.rs.bk",
        ".DS_Store", "Thumbs.db",
    ],
    "java": [
        "target/", "build/", ".gradle/", "*.class", "*.jar", "*.war",
        ".idea/", "*.iml",
        ".DS_Store", "Thumbs.db",
    ],
    "ruby": [
        "vendor/bundle/", ".bundle/", "*.gem", "*.rbc",
        "coverage/", "spec/reports/",
        ".DS_Store", "Thumbs.db",
    ],
    "general": [
        ".DS_Store", "Thumbs.db",
        ".env", ".env.local",
        "*.log", "logs/",
        "*.tmp", "*.temp",
        ".vscode/", ".idea/", "*.swp", "*.swo",
    ],
}

PROJECT_MARKERS = {
    "nodejs":  {"required": ["package.json"], "optional": ["node_modules", "yarn.lock", "pnpm-lock.yaml", "package-lock.json", ".nvmrc"]},
    "python":  {"required": ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile"], "optional": ["__pycache__", ".venv", "venv"]},
    "go":      {"required": ["go.mod"], "optional": ["go.sum", "vendor"]},
    "rust":    {"required": ["Cargo.toml"], "optional": ["Cargo.lock", "target"]},
    "java":    {"required": ["pom.xml", "build.gradle", "build.gradle.kts"], "optional": ["target", "build", ".gradle"]},
    "ruby":    {"required": ["Gemfile"], "optional": ["Gemfile.lock", "vendor/bundle"]},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd, cwd=None, check=False):
    """Run a command and return CompletedProcess.

    Args:
        cmd: Command as a list of strings, or a string for simple commands.
    """
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, check=check)


def detect_project_type(cwd):
    """Score-based project type detection. Returns (type, detected_files, score)."""
    scores = {}
    detected = {}
    for lang, markers in PROJECT_MARKERS.items():
        score = 0
        files = []
        for f in markers["required"]:
            if (Path(cwd) / f).exists():
                score += 10
                files.append(f)
                break
        for f in markers["optional"]:
            if (Path(cwd) / f).exists():
                score += 2
                files.append(f)
        if score > 0:
            scores[lang] = score
            detected[lang] = files
    if not scores:
        return None, [], 0
    best = max(scores, key=scores.get)
    return best, detected[best], scores[best]


def detect_git_status(cwd):
    """Detect git initialization status."""
    has_git = (Path(cwd) / ".git").exists()
    has_remote = False
    remote_url = None
    has_commits = False
    current_branch = None

    if has_git:
        r = run("git remote get-url origin", cwd=cwd)
        if r.returncode == 0 and r.stdout.strip():
            has_remote = True
            remote_url = r.stdout.strip()
        r = run("git rev-list --count HEAD", cwd=cwd)
        if r.returncode == 0:
            has_commits = int(r.stdout.strip()) > 0
        r = run("git branch --show-current", cwd=cwd)
        if r.returncode == 0 and r.stdout.strip():
            current_branch = r.stdout.strip()

    return {
        "has_git": has_git,
        "has_remote": has_remote,
        "remote_url": remote_url,
        "has_commits": has_commits,
        "current_branch": current_branch,
    }


def detect_sensitive_files(cwd):
    """Find .env files or credential-like files that shouldn't be committed."""
    patterns = [".env", ".env.local", ".env.production", "credentials.json", "*.pem", "*.key"]
    found = []
    for p in patterns:
        if "*" in p:
            found.extend(str(f.relative_to(cwd)) for f in Path(cwd).glob(p))
        elif (Path(cwd) / p).exists():
            found.append(p)
    return found


# ---------------------------------------------------------------------------
# detect subcommand
# ---------------------------------------------------------------------------

def cmd_detect(args):
    cwd = str(Path(args.path).resolve())
    proj_type, proj_files, confidence = detect_project_type(cwd)
    git = detect_git_status(cwd)
    sensitive = detect_sensitive_files(cwd)
    has_gitignore = (Path(cwd) / ".gitignore").exists()

    result = {
        "cwd": cwd,
        "suggested_repo_name": Path(cwd).name,
        "project_type": proj_type,
        "detected_files": proj_files,
        "confidence": confidence,
        "suggested_gitignore": proj_type or "general",
        "has_gitignore": has_gitignore,
        "sensitive_files": sensitive,
        **git,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# init subcommand
# ---------------------------------------------------------------------------

def cmd_init(args):
    cwd = os.getcwd()
    dry = args.dry_run
    steps = []
    errors = []

    def step(msg):
        steps.append(msg)
        print(f"  {'[DRY-RUN] ' if dry else ''}+ {msg}")

    def fail(msg):
        errors.append(msg)
        print(f"  ! {msg}", file=sys.stderr)

    # ---- prerequisites ----
    r = run("git --version")
    if r.returncode != 0:
        fail("git is not installed. Install git first.")
        _summary(False, steps, errors)
        return
    r = run("gh auth status")
    if r.returncode != 0:
        fail("gh CLI is not authenticated. Run: gh auth login")
        _summary(False, steps, errors)
        return

    # ---- detect ----
    proj_type, _, _ = detect_project_type(cwd)
    git = detect_git_status(cwd)

    # ---- .gitignore ----
    gitignore_path = Path(cwd) / ".gitignore"
    if args.skip_gitignore:
        step("Skipping .gitignore generation")
    else:
        template_key = proj_type or "general"
        new_entries = GITIGNORE_TEMPLATES.get(template_key, GITIGNORE_TEMPLATES["general"])
        sensitive = detect_sensitive_files(cwd)
        for s in sensitive:
            if s not in new_entries:
                new_entries.append(s)

        if gitignore_path.exists():
            existing = gitignore_path.read_text().splitlines()
            existing_set = {l.strip().lower() for l in existing if l.strip() and not l.startswith("#")}
            unique = [e for e in new_entries if e.strip().lower() not in existing_set]
            if unique:
                if not dry:
                    with gitignore_path.open("a") as f:
                        f.write("\n# Added by github-init\n")
                        for entry in unique:
                            f.write(f"{entry}\n")
                step(f"Merged {len(unique)} entries into existing .gitignore ({template_key})")
            else:
                step(".gitignore already up-to-date")
        else:
            if not dry:
                with gitignore_path.open("w") as f:
                    f.write(f"# {template_key} .gitignore\n")
                    for entry in new_entries:
                        f.write(f"{entry}\n")
            step(f"Created .gitignore ({template_key}, {len(new_entries)} entries)")

    # ---- git init ----
    if not git["has_git"]:
        if not dry:
            run("git init", cwd=cwd, check=True)
        step("Initialized git repository")
    else:
        step("Git already initialized")

    # ---- branch ----
    branch = git["current_branch"] or "main"
    if not git["has_commits"] and branch != "main":
        if not dry:
            run("git branch -M main", cwd=cwd)
        branch = "main"
        step("Set default branch to main")

    # ---- initial commit ----
    if not git["has_commits"]:
        if not dry:
            run("git add .", cwd=cwd, check=True)
            run(["git", "commit", "-m", "Initial commit"], cwd=cwd, check=True)
        step("Created initial commit")
    else:
        # Stage any unstaged changes
        r = run("git status --porcelain", cwd=cwd)
        if r.stdout.strip():
            if not dry:
                run("git add .", cwd=cwd, check=True)
                run(["git", "commit", "-m", "Initial commit"], cwd=cwd, check=True)
            step("Committed unstaged changes")
        else:
            step("All changes already committed")

    # ---- GitHub repo ----
    repo_name = args.name or Path(cwd).name
    vis_flag = "--public" if args.visibility == "public" else "--private"

    if git["has_remote"]:
        step(f"Remote already exists: {git['remote_url']}")
    else:
        gh_cmd = ["gh", "repo", "create", repo_name, "--source=.", vis_flag, "--push"]
        if args.description:
            gh_cmd.extend(["--description", args.description])
        if not dry:
            r = run(gh_cmd, cwd=cwd)
            if r.returncode != 0:
                if "already exists" in r.stderr:
                    fail(f"Repository '{repo_name}' already exists on GitHub. Use a different --name.")
                    _summary(False, steps, errors)
                    return
                else:
                    fail(f"gh repo create failed: {r.stderr.strip()}")
                    _summary(False, steps, errors)
                    return
            step(f"Created GitHub repo: {repo_name} ({args.visibility})")
        else:
            step(f"Would create GitHub repo: {repo_name} ({args.visibility})")

    # ---- push (if gh repo create didn't already push) ----
    if not git["has_remote"] and not dry:
        r = run("git remote get-url origin", cwd=cwd)
        if r.returncode == 0:
            repo_url = r.stdout.strip()
            step(f"Pushed to {repo_url}")

    # ---- summary ----
    _summary(len(errors) == 0, steps, errors, repo_name=repo_name)


def _summary(success, steps, errors, repo_name=None):
    print()
    if success:
        print(f"Done! Repository '{repo_name}' is ready.")
    else:
        print("Failed. See errors above.")
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GitHub Repository Initialization")
    sub = parser.add_subparsers(dest="command", required=True)

    # detect
    p_detect = sub.add_parser("detect", help="Detect project type and git status")
    p_detect.add_argument("path", nargs="?", default=".", help="Project directory")

    # init
    p_init = sub.add_parser("init", help="Initialize git + GitHub repo")
    p_init.add_argument("--name", help="Repository name (default: directory name)")
    p_init.add_argument("--visibility", choices=["public", "private"], default="private")
    p_init.add_argument("--description", help="Repository description")
    p_init.add_argument("--skip-gitignore", action="store_true", help="Skip .gitignore generation")
    p_init.add_argument("--dry-run", action="store_true", help="Preview mode, no changes made")

    args = parser.parse_args()
    if args.command == "detect":
        cmd_detect(args)
    elif args.command == "init":
        cmd_init(args)


if __name__ == "__main__":
    main()
