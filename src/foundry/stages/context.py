from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .. import state
from ..config import Settings
from ..models import Task

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
}

LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".css": "CSS",
    ".html": "HTML",
    ".md": "Markdown",
    ".toml": "TOML",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".sh": "Shell",
}

MANIFEST_NAMES = {
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    "poetry.lock",
    "uv.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.toml",
    "go.mod",
    "Makefile",
    "docker-compose.yml",
    "Dockerfile",
}

TEXT_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".css",
    ".html",
    ".md",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".txt",
    ".sh",
}

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "you",
    "your",
    "into",
    "add",
    "make",
    "сейчас",
    "сделать",
    "для",
    "как",
    "что",
    "это",
    "или",
    "уже",
    "минимум",
    "настоящим",
    "настоящая",
}


def run(
    task: Task,
    settings: Settings,
    repo_path: Path | None = None,
) -> dict:
    """Build a compact repository context for the planning agent."""
    root = _resolve_repo_path(task, repo_path)
    files = _iter_repo_files(root)
    languages = _languages(files)
    manifests = _manifest_files(root, files)
    keywords = _issue_keywords(task)
    relevant_files = _relevant_files(root, files, keywords)
    test_commands = _test_commands(root, settings, manifests)
    state.init_db(settings.db_path)
    repo_memory = state.list_repo_memory(settings.db_path, task.repo)

    return {
        "repo": task.repo,
        "root": str(root),
        "languages": languages,
        "manifest_files": manifests,
        "test_commands": test_commands,
        "keywords": keywords,
        "relevant_files": relevant_files,
        "repo_memory": repo_memory,
        "files": [f["path"] for f in relevant_files],
    }


def format_for_prompt(ctx: dict) -> str:
    """Render context as stable markdown for the planner prompt."""
    lines = ["## Repository context", ""]
    if ctx.get("languages"):
        lines.append("### Languages")
        for item in ctx["languages"]:
            lines.append(f"- {item['language']}: {item['files']} files")
        lines.append("")
    if ctx.get("manifest_files"):
        lines.append("### Manifest files")
        lines.extend(f"- `{path}`" for path in ctx["manifest_files"])
        lines.append("")
    if ctx.get("test_commands"):
        lines.append("### Likely test commands")
        lines.extend(f"- `{cmd}`" for cmd in ctx["test_commands"])
        lines.append("")
    if ctx.get("keywords"):
        lines.append("### Issue keywords")
        lines.append(", ".join(f"`{kw}`" for kw in ctx["keywords"]))
        lines.append("")
    if ctx.get("relevant_files"):
        lines.append("### Relevant files")
        for item in ctx["relevant_files"]:
            matched = ", ".join(item.get("matched_keywords", []))
            suffix = f" ({matched})" if matched else ""
            lines.append(f"- `{item['path']}`{suffix}")
        lines.append("")
    if ctx.get("repo_memory"):
        lines.append("### Repo memory")
        for item in ctx["repo_memory"]:
            lines.append(f"- `{item['key']}`: {_format_memory_value(item.get('value'))}")
    return "\n".join(lines).strip()


def _format_memory_value(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(f"`{str(item)}`" for item in value[:12]) or "[]"
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in list(value.items())[:8]:
            if isinstance(item, list):
                rendered = ", ".join(f"`{str(v)}`" for v in item[:6])
            else:
                rendered = f"`{item}`"
            parts.append(f"{key}: {rendered}")
        return "; ".join(parts) or "{}"
    return f"`{value}`"


def _resolve_repo_path(task: Task, repo_path: Path | None) -> Path:
    if repo_path is not None:
        return repo_path.resolve()
    if task.worktree_path:
        return Path(task.worktree_path).resolve()
    return Path.cwd().resolve()


def _iter_repo_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            out.append(path)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def _languages(files: list[Path]) -> list[dict[str, object]]:
    counts: Counter[str] = Counter()
    for path in files:
        language = LANGUAGE_EXTENSIONS.get(path.suffix)
        if language:
            counts[language] += 1
    return [
        {"language": language, "files": count}
        for language, count in counts.most_common()
    ]


def _manifest_files(root: Path, files: list[Path]) -> list[str]:
    return [
        path.relative_to(root).as_posix()
        for path in files
        if path.name in MANIFEST_NAMES
    ]


def _issue_keywords(task: Task) -> list[str]:
    text = f"{task.issue_title}\n{task.issue_body}".lower()
    tokens = re.findall(r"[\w-]{3,}", text, flags=re.UNICODE)
    keywords: list[str] = []
    for token in tokens:
        normalized = token.strip("-_")
        if not normalized or normalized in STOPWORDS:
            continue
        if normalized.isdigit():
            continue
        if normalized not in keywords:
            keywords.append(normalized)
    return keywords[:20]


def _relevant_files(
    root: Path,
    files: list[Path],
    keywords: list[str],
    *,
    limit: int = 12,
) -> list[dict[str, object]]:
    if not keywords:
        return []

    scored: list[tuple[int, str, list[str]]] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        if path.suffix and path.suffix not in TEXT_EXTENSIONS:
            continue
        if path.stat().st_size > 200_000:
            continue

        haystacks = [rel.lower()]
        text = _read_text(path)
        if text:
            haystacks.append(text.lower())

        matched: list[str] = []
        score = 0
        for keyword in keywords:
            path_hits = haystacks[0].count(keyword)
            body_hits = haystacks[1].count(keyword) if len(haystacks) > 1 else 0
            if path_hits or body_hits:
                matched.append(keyword)
                score += (path_hits * 5) + min(body_hits, 5)
        if score:
            scored.append((score, rel, matched))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        {"path": rel, "score": score, "matched_keywords": matched}
        for score, rel, matched in scored[:limit]
    ]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _test_commands(
    root: Path,
    settings: Settings,
    manifests: list[str],
) -> list[str]:
    if settings.verify_commands is not None:
        return [" ".join(cmd) for cmd in settings.verify_commands]

    commands: list[str] = []
    manifest_set = set(manifests)
    if "pyproject.toml" in manifest_set:
        commands.append("ruff check .")
        if (root / "tests").is_dir():
            commands.append("pytest -x --no-header -q")
    if "package.json" in manifest_set:
        commands.append("npm test --silent")
    if "Cargo.toml" in manifest_set:
        commands.append("cargo test")
    if "go.mod" in manifest_set:
        commands.append("go test ./...")

    for manifest in manifests:
        if manifest.endswith("/package.json"):
            package_dir = Path(manifest).parent.as_posix()
            commands.append(f"npm --prefix {package_dir} test --silent")

    return _dedupe(commands)


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out
