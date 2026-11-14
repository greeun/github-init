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
#
# A template is a list of (section comment, [patterns]) pairs instead of a flat
# list. Sections keep related patterns adjacent in the generated file, and that
# adjacency is load-bearing for negation: git resolves "!" exceptions by
# last-match-wins, so "!.env*.example" only keeps working while it sits after
# ".env*". Grouping them lets the merge step move a section as one unit.
# ---------------------------------------------------------------------------

ENV_SECTION = (
    "env files (example and template files stay tracked)",
    [".env*", "!.env*.example", "!.env*.template"],
)

EDITOR_SECTION = ("editors", [".idea/", ".vscode/", "*.swp", "*.swo"])

OS_SECTION = ("OS", [".DS_Store", "Thumbs.db"])

# Local state written by coding agents and their tooling. None of it describes
# the project, and some of it (CLAUDE.md, MCP config) is personal enough that
# committing it leaks how an individual works rather than how the code works.
# Every project type gets this block, since the tooling is language-agnostic.
#
# The patterns are deliberately narrower than a bare ".ast*" or ".axt*" prefix:
# ".ast*" would also swallow Astro's ".astro/" cache directory, which is a real
# build artifact some projects do want to reason about separately.
AGENT_TOOLING_SECTIONS = [
    (
        "claude code (instructions, local settings, session worktrees, MCP config)",
        ["CLAUDE.md", ".claude/", ".claude.json", ".claude.json.*", ".claude-*.json"],
    ),
    (
        "superpowers (auto-installed working notes)",
        [".superpowers/", "docs/superpowers/"],
    ),
    ("axt local profile (including backups)", [".axt/", ".axt-*", ".axt.*"]),
    ("ast (agent session tracker) local state", [".ast/", ".ast-*", ".ast.*"]),
]

GITIGNORE_TEMPLATES = {
    "nodejs": [
        ("dependencies", ["node_modules/"]),
        ("build output", ["dist/", "build/", ".next/", "out/", "*.tsbuildinfo"]),
        (
            "logs",
            ["*.log", "npm-debug.log*", "yarn-debug.log*", "yarn-error.log*",
             "pnpm-debug.log*", "logs/"],
        ),
        ("test output", ["coverage/", ".nyc_output/"]),
        ("caches", [".cache/", ".turbo/", ".eslintcache"]),
        ENV_SECTION,
        EDITOR_SECTION,
        OS_SECTION,
    ],
    "python": [
        ("byte-compiled", ["__pycache__/", "*.py[cod]", "*$py.class"]),
        ("virtualenvs", [".venv/", "venv/"]),
        ("build output", ["build/", "dist/", "*.egg-info/", "*.egg"]),
        ("test output", [".pytest_cache/", ".coverage", "htmlcov/", ".tox/"]),
        ("notebooks", [".ipynb_checkpoints/"]),
        ("caches", [".mypy_cache/", ".ruff_cache/"]),
        ENV_SECTION,
        EDITOR_SECTION,
        OS_SECTION,
    ],
    "go": [
        ("binaries", ["*.exe", "*.exe~", "*.dll", "*.so", "*.dylib"]),
        ("test output", ["*.test", "*.out"]),
        ("modules", ["vendor/", "go.work", "go.work.sum"]),
        ENV_SECTION,
        EDITOR_SECTION,
        OS_SECTION,
    ],
    "rust": [
        ("build output", ["/target/", "**/*.rs.bk"]),
        ENV_SECTION,
        EDITOR_SECTION,
        OS_SECTION,
    ],
    "java": [
        ("build output", ["target/", "build/", ".gradle/", "*.class", "*.jar", "*.war"]),
        ("editors", [".idea/", "*.iml", ".vscode/", "*.swp", "*.swo"]),
        ENV_SECTION,
        OS_SECTION,
    ],
    "ruby": [
        ("dependencies", ["vendor/bundle/", ".bundle/"]),
        ("build output", ["*.gem", "*.rbc"]),
        ("test output", ["coverage/", "spec/reports/"]),
        ENV_SECTION,
        EDITOR_SECTION,
        OS_SECTION,
    ],
    "general": [
        ("logs", ["*.log", "logs/"]),
        ("temporary files", ["*.tmp", "*.temp"]),
        ENV_SECTION,
        EDITOR_SECTION,
        OS_SECTION,
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

# A committed lockfile is an instruction to everyone who installs next, so two
# of them in one repository is a contradiction. Whichever one is present tells
# us the package manager in use; the others are strays worth ignoring.
LOCKFILES = {
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "package-lock.json": "npm",
    "bun.lockb": "bun",
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


def detect_package_manager(cwd):
    """Identify the Node package manager from the lockfile that is present.

    Returns (manager, lockfile, stray_lockfiles). When zero or several
    lockfiles exist we cannot tell which one is authoritative, so we report
    nothing and leave every lockfile tracked -- guessing here would ignore the
    file the project actually depends on.
    """
    present = [name for name in LOCKFILES if (Path(cwd) / name).exists()]
    if len(present) != 1:
        return None, None, []
    lock = present[0]
    return LOCKFILES[lock], lock, [n for n in LOCKFILES if n != lock]


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


def tracked_but_ignored(cwd):
    """Files git tracks that the ignore rules also match.

    Adding a pattern never untracks anything, so these files keep being
    committed while .gitignore claims they are out of the repository. The
    contradiction is what bites later: someone reads the ignore file, assumes
    the file is gone, and is surprised when their edit to it lands in a diff.

    Entries the index still holds but the working tree no longer has are left
    out. Those are pending deletions, and the author clearly wants them gone --
    resurrecting them with an exception would undo the removal they started.
    """
    r = run("git ls-files --ignored --exclude-standard -c", cwd=cwd)
    if r.returncode != 0:
        return []
    return [
        line.strip()
        for line in r.stdout.splitlines()
        if line.strip() and (Path(cwd) / line.strip()).exists()
    ]


# ---------------------------------------------------------------------------
# .gitignore composition
# ---------------------------------------------------------------------------

def build_sections(cwd, template_key):
    """Assemble the sections for a project: template + package manager + agents."""
    sections = list(GITIGNORE_TEMPLATES.get(template_key, GITIGNORE_TEMPLATES["general"]))

    if template_key == "nodejs":
        manager, lock, strays = detect_package_manager(cwd)
        if manager:
            sections.append((
                f"this project uses {manager} ({lock}); other lockfiles are strays",
                strays,
            ))

    sections.extend(AGENT_TOOLING_SECTIONS)
    return sections


def render_sections(sections, header=None):
    """Render (comment, patterns) pairs as .gitignore text."""
    lines = [header] if header else []
    for comment, patterns in sections:
        if not patterns:
            continue
        if lines:
            lines.append("")
        lines.append(f"# {comment}")
        lines.extend(patterns)
    return "\n".join(lines) + "\n"


def existing_patterns(text):
    """Patterns already in the file, lowercased, for case-insensitive dedup."""
    return {
        line.strip().lower()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def plan_merge(existing_text, sections):
    """Work out what to append to an existing .gitignore.

    Returns (sections_to_append, restated_negations, added_pattern_count).

    Deduplication alone is not enough here, because order decides what a "!"
    line means. Two rules keep the merged file behaving the way it reads:

    - A section containing "!" exceptions is appended whole as soon as any of
      its patterns is new. Appending only the missing half would strand the
      exception above the pattern it overrides, and git would go on ignoring a
      file the author meant to track.
    - Exceptions already in the file are restated at the end. Everything we add
      lands below them, so without this an added ".env*" would silently cancel
      an existing "!.env.example".
    """
    have = existing_patterns(existing_text)
    to_append = []
    added = 0

    for comment, patterns in sections:
        missing = [p for p in patterns if p.strip().lower() not in have]
        if not missing:
            continue
        if any(p.startswith("!") for p in patterns):
            to_append.append((comment, list(patterns)))
        else:
            to_append.append((comment, missing))
        added += len(missing)
        have.update(p.strip().lower() for p in patterns)

    if not to_append:
        return [], [], 0

    appended_lower = {
        p.strip().lower() for _, patterns in to_append for p in patterns
    }
    restated = [
        line.strip()
        for line in existing_text.splitlines()
        if line.strip().startswith("!") and line.strip().lower() not in appended_lower
    ]
    return to_append, restated, added


def tracked_files(cwd):
    """Paths git tracks, or an empty set when there is no repository yet."""
    r = run("git ls-files", cwd=cwd)
    if r.returncode != 0:
        return set()
    return {line.strip() for line in r.stdout.splitlines() if line.strip()}


def is_literal(pattern):
    """A pattern naming one file rather than a glob, a directory or an exception."""
    return not (
        pattern.startswith("!")
        or pattern.endswith("/")
        or any(ch in pattern for ch in "*?[")
    )


def drop_tracked_literals(sections, tracked):
    """Remove literal patterns that name a file the repository already tracks.

    The template's literals (such as CLAUDE.md in the agent tooling block) are
    there because in most projects those files are not part of the project.
    When the repository tracks one, the author has decided otherwise. Writing
    the pattern and then a "!<path>" exception for it would only leave two
    contradicting lines, so the pattern is not written at all.

    A literal without a slash matches at any depth, the way git reads it; a
    literal with a slash is anchored to the repository root.
    """
    names = {Path(p).name for p in tracked}
    kept, dropped = [], []
    for comment, patterns in sections:
        keep = []
        for p in patterns:
            if is_literal(p):
                bare = p.lstrip("/")
                hit = bare in tracked if "/" in p else bare in names
                if hit:
                    dropped.append(p)
                    continue
            keep.append(p)
        kept.append((comment, keep))
    return kept, dropped


def update_gitignore(cwd, proj_type, git, dry, step, warn):
    """Create or merge .gitignore. Never stages, commits or pushes anything."""
    gitignore_path = Path(cwd) / ".gitignore"
    template_key = proj_type or "general"
    sections = build_sections(cwd, template_key)

    # Anything credential-shaped that the template does not already cover
    # deserves its own line, so the reason it is ignored stays readable.
    covered = {p.strip().lower() for _, patterns in sections for p in patterns}
    extra_sensitive = [s for s in detect_sensitive_files(cwd) if s.lower() not in covered]
    if extra_sensitive:
        sections.append(("credentials found in this directory", extra_sensitive))

    if git["has_git"]:
        sections, dropped = drop_tracked_literals(sections, tracked_files(cwd))
        if dropped:
            step(f"Left out pattern(s) naming tracked files: {', '.join(dropped)}")

    if template_key == "nodejs":
        manager, lock, _ = detect_package_manager(cwd)
        if manager:
            step(f"Detected package manager: {manager} ({lock})")
        elif any((Path(cwd) / n).exists() for n in LOCKFILES):
            warn("Multiple lockfiles present; leaving all of them tracked")

    if gitignore_path.exists():
        existing = gitignore_path.read_text()
        to_append, restated, added = plan_merge(existing, sections)
        if added:
            body = render_sections(to_append, header="# Added by github-init")
            if restated:
                body += "\n" + render_sections(
                    [("exceptions restated so the rules above cannot cancel them", restated)]
                )
            if not dry:
                with gitignore_path.open("a") as f:
                    if not existing.endswith("\n"):
                        f.write("\n")
                    f.write("\n" + body)
            step(f"Merged {added} entries into existing .gitignore ({template_key})")
            if restated:
                step(f"Restated {len(restated)} exception(s) to preserve their effect")
            for line in body.splitlines():
                if line.strip():
                    print(f"      {line}")
        else:
            step(".gitignore already up-to-date")
    else:
        content = render_sections(sections, header=f"# {template_key} .gitignore")
        if not dry:
            gitignore_path.write_text(content)
        count = sum(len(p) for _, p in sections)
        step(f"Created .gitignore ({template_key}, {count} entries)")

    # ---- verify against what git already tracks ----
    # Only meaningful once a repository exists: a fresh directory tracks
    # nothing, so there is no contradiction to find yet.
    if git["has_git"] and not dry:
        conflicts = tracked_but_ignored(cwd)
        if conflicts:
            exceptions = [f"!{path}" for path in conflicts]
            with gitignore_path.open("a") as f:
                f.write("\n" + render_sections([(
                    "already tracked, so kept tracked despite the rules above",
                    exceptions,
                )]))
            warn(
                f"{len(conflicts)} tracked file(s) matched the new rules; "
                f"added exceptions to keep them tracked: {', '.join(conflicts[:5])}"
                + (" ..." if len(conflicts) > 5 else "")
            )
        else:
            step("No tracked file is matched by the new rules")
    elif git["has_git"] and dry:
        step("Would verify the new rules against tracked files")


# ---------------------------------------------------------------------------
# detect subcommand
# ---------------------------------------------------------------------------

def cmd_detect(args):
    cwd = str(Path(args.path).resolve())
    proj_type, proj_files, confidence = detect_project_type(cwd)
    git = detect_git_status(cwd)
    sensitive = detect_sensitive_files(cwd)
    has_gitignore = (Path(cwd) / ".gitignore").exists()
    manager, lock, strays = detect_package_manager(cwd)

    result = {
        "cwd": cwd,
        "suggested_repo_name": Path(cwd).name,
        "project_type": proj_type,
        "detected_files": proj_files,
        "confidence": confidence,
        "suggested_gitignore": proj_type or "general",
        "has_gitignore": has_gitignore,
        "package_manager": manager,
        "lockfile": lock,
        "stray_lockfiles": strays,
        "sensitive_files": sensitive,
        "tracked_but_ignored": tracked_but_ignored(cwd) if git["has_git"] else [],
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
    warnings = []

    def step(msg):
        steps.append(msg)
        print(f"  {'[DRY-RUN] ' if dry else ''}+ {msg}")

    def warn(msg):
        warnings.append(msg)
        print(f"  ~ {msg}")

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
    if args.skip_gitignore:
        step("Skipping .gitignore generation")
    else:
        update_gitignore(cwd, proj_type, git, dry, step, warn)

    # ---- git init ----
    if not git["has_git"]:
        if not dry:
            run("git init", cwd=cwd, check=True)
        step("Initialized git repository")
    else:
        step("Git already initialized")

    # ---- branch ----
    # Re-detect the branch AFTER git init: the earlier detection ran before the
    # repo existed (current_branch was None), so on environments whose git default
    # is still "master" the rename would never fire. Query the real branch now.
    if not dry:
        r = run("git branch --show-current", cwd=cwd)
        actual_branch = r.stdout.strip() if r.returncode == 0 else ""
    else:
        actual_branch = git["current_branch"] or ""
    branch = actual_branch or "main"
    if not git["has_commits"] and actual_branch and actual_branch != "main":
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
    _summary(len(errors) == 0, steps, errors, repo_name=repo_name, warnings=warnings)


def cmd_gitignore(args):
    """Update .gitignore alone: no gh, no commit, no remote.

    Kept apart from init because an existing repository usually has its own
    branch rules and commit conventions. The change is left in the working tree
    for the caller to review and commit on the branch they choose.
    """
    cwd = os.path.abspath(args.path)
    dry = args.dry_run
    warnings = []

    def step(msg):
        print(f"  {'[DRY-RUN] ' if dry else ''}+ {msg}")

    def warn(msg):
        warnings.append(msg)
        print(f"  ~ {msg}")

    proj_type, _, _ = detect_project_type(cwd)
    git = detect_git_status(cwd)
    update_gitignore(cwd, proj_type, git, dry, step, warn)

    print()
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  - {w}")
        print()
    if dry:
        print("Dry run: .gitignore was not changed.")
    elif git["has_git"]:
        print("Done. Review with `git diff .gitignore`; nothing was staged or committed.")
    else:
        print("Done. No git repository here yet; nothing was staged or committed.")


def _summary(success, steps, errors, repo_name=None, warnings=None):
    print()
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  - {w}")
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

    # gitignore
    p_ignore = sub.add_parser("gitignore", help="Create or merge .gitignore only (no commit, no remote)")
    p_ignore.add_argument("path", nargs="?", default=".", help="Project directory")
    p_ignore.add_argument("--dry-run", action="store_true", help="Preview mode, no changes made")

    args = parser.parse_args()
    if args.command == "detect":
        cmd_detect(args)
    elif args.command == "init":
        cmd_init(args)
    elif args.command == "gitignore":
        cmd_gitignore(args)


if __name__ == "__main__":
    main()
