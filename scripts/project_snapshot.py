#!/usr/bin/env python3

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


# ============================================================
# Configuration
# ============================================================

OUTPUT_FILE = "project_snapshot.md"

MAX_FILE_SIZE = 1024 * 4096  # 4 MB

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",

    "node_modules",

    ".venv",
    "venv",
    "env",

    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",

    ".tox",
    ".nox",

    "dist",
    "build",
    "out",

    ".idea",
    ".vscode",

    "coverage",
    ".coverage",

    ".next",
    ".nuxt",
    ".turbo",

    "target",
    "vendor",
}

EXCLUDED_FILES = {
    OUTPUT_FILE,

    ".env",
    ".env.local",
    ".env.production",
    ".env.development",

    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",

    "Todo.md",
    "Agent.md",
    "ProjectStructure.md",
    "project_snapshot.md",
}

INCLUDED_EXTENSIONS = {
    # Python
    ".py",
    ".pyi",

    # JavaScript / TypeScript
    ".js",
    ".jsx",
    ".ts",
    ".tsx",

    # Frontend
    ".vue",
    ".html",
    ".css",
    ".scss",
    ".sass",
    ".less",

    # Data / configuration
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",

    # Qt
    ".qrc",
    ".ui",

    # Documentation
    ".md",
    ".txt",

    # Shell
    ".sh",
    ".bash",
    ".zsh",

    # C / C++
    ".c",
    ".h",
    ".cpp",
    ".hpp",

    # Java / Kotlin
    ".java",
    ".kt",

    # C#
    ".cs",

    # Go / Rust
    ".go",
    ".rs",

    # PHP
    ".php",

    # Ruby
    ".rb",

    # Swift
    ".swift",

    # SQL
    ".sql",

    # Docker
    ".dockerfile",
}

EXCLUDED_EXTENSIONS = {
    # Executables
    ".exe",
    ".dll",
    ".so",
    ".dylib",

    # Compiled
    ".pyc",
    ".pyo",
    ".class",
    ".o",
    ".obj",

    # Images
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".ico",
    ".svg",

    # Audio
    ".mp3",
    ".wav",
    ".flac",
    ".ogg",
    ".m4a",

    # Video
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".webm",

    # Archives
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",

    # Databases
    ".db",
    ".sqlite",
    ".sqlite3",

    # Logs
    ".log",

    # Certificates / keys
    ".pem",
    ".key",
    ".crt",
    ".cer",
}


# ============================================================
# Helpers
# ============================================================

def is_excluded_dir(name: str) -> bool:
    return name in EXCLUDED_DIRS


def is_excluded_file(name: str) -> bool:
    if name in EXCLUDED_FILES:
        return True

    lower = name.lower()

    secret_names = (
        ".env",
        ".secret",
        "secret.",
        "credentials.",
        "credential.",
    )

    return lower.startswith(secret_names)


def should_include_file(name: str) -> bool:
    if is_excluded_file(name):
        return False

    suffix = Path(name).suffix.lower()

    special_files = {
        "Dockerfile",
        "Makefile",
        "CMakeLists.txt",
        "Procfile",
        ".gitignore",
        ".dockerignore",
        ".editorconfig",
    }

    if name in special_files:
        return True

    if suffix in EXCLUDED_EXTENSIONS:
        return False

    return suffix in INCLUDED_EXTENSIONS


def read_text_file(path: Path) -> str:
    try:
        content = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        # Compact whitespace without changing code indentation.
        lines = content.replace(
            "\r\n", "\n"
        ).replace(
            "\r", "\n"
        ).splitlines()

        cleaned = []
        previous_blank = False

        for line in lines:
            line = line.rstrip()

            if not line:
                if previous_blank:
                    continue

                previous_blank = True
                cleaned.append("")
            else:
                previous_blank = False
                cleaned.append(line)

        return "\n".join(cleaned).strip()

    except OSError as exc:
        return f"[Unable to read file: {exc}]"


# ============================================================
# Project Scanner
# ============================================================

def scan_project(root: Path) -> list[Path]:
    files: list[Path] = []

    stack = [root]

    while stack:
        current = stack.pop()

        try:
            entries = list(os.scandir(current))
        except (PermissionError, OSError):
            continue

        directories = []
        current_files = []

        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    if not is_excluded_dir(entry.name):
                        directories.append(Path(entry.path))

                elif entry.is_file(follow_symlinks=False):
                    if should_include_file(entry.name):
                        current_files.append(Path(entry.path))

            except OSError:
                continue

        directories.sort(
            key=lambda p: p.name.lower(),
            reverse=True,
        )

        current_files.sort(
            key=lambda p: p.name.lower()
        )

        stack.extend(directories)
        files.extend(current_files)

    files.sort(
        key=lambda p: p.relative_to(root).as_posix().lower()
    )

    return files


# ============================================================
# Tree
# ============================================================

def build_tree(root: Path, files: list[Path]) -> list[str]:
    tree: dict = {}

    for file in files:
        relative = file.relative_to(root)
        parts = relative.parts

        current = tree

        for part in parts[:-1]:
            current = current.setdefault(part, {})

        current.setdefault("__files__", []).append(parts[-1])

    lines: list[str] = []

    def render(node: dict, prefix: str = "") -> None:
        directories = sorted(
            (
                key
                for key in node
                if key != "__files__"
            ),
            key=str.lower,
        )

        file_names = sorted(
            node.get("__files__", []),
            key=str.lower,
        )

        entries = directories + file_names

        for index, name in enumerate(entries):
            is_last = index == len(entries) - 1

            connector = (
                "└── "
                if is_last
                else "├── "
            )

            lines.append(
                f"{prefix}{connector}{name}"
            )

            if name in directories:
                child_prefix = prefix + (
                    "    "
                    if is_last
                    else "│   "
                )

                render(
                    node[name],
                    child_prefix,
                )

    render(tree)

    return lines


# ============================================================
# Compact Markdown generation
# ============================================================

def generate_snapshot(
    root: Path,
    files: list[Path],
) -> str:

    total_size = 0

    for file in files:
        try:
            total_size += file.stat().st_size
        except OSError:
            pass

    output: list[str] = []

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    output.append("# PROJECT SNAPSHOT")
    output.append(f"root={root}")
    output.append(f"files={len(files)}")
    output.append(
        f"size={total_size / 1024 / 1024:.2f}MB"
    )

    # --------------------------------------------------------
    # Tree
    # --------------------------------------------------------

    output.append("")
    output.append("# TREE")
    output.extend(
        build_tree(root, files)
    )

    # --------------------------------------------------------
    # File contents
    # --------------------------------------------------------

    output.append("")
    output.append("# FILES")

    for file in files:
        relative = file.relative_to(root).as_posix()

        try:
            size = file.stat().st_size
        except OSError:
            size = 0

        output.append("")
        output.append(f"[{relative}]")

        if size > MAX_FILE_SIZE:
            output.append(
                f"[SKIPPED: {size / 1024 / 1024:.2f}MB]"
            )
            continue

        content = read_text_file(file)

        if content:
            output.append(content)
        else:
            output.append("[EMPTY]")

    return "\n".join(output) + "\n"


# ============================================================
# Main
# ============================================================

def main() -> None:
    # Start from one directory above the script's location.
    script_dir = Path(__file__).resolve().parent
    root = script_dir.parent

    output_path = root / OUTPUT_FILE

    print(f"Project root: {root}")
    print("Scanning project...")

    files = scan_project(root)

    print(
        f"Found {len(files)} source/configuration files."
    )

    print("Generating compact snapshot...")

    content = generate_snapshot(
        root,
        files,
    )

    output_path.write_text(
        content,
        encoding="utf-8",
        newline="\n",
    )

    size_mb = output_path.stat().st_size / 1024 / 1024

    print()
    print("Snapshot created successfully.")
    print(f"Output: {output_path}")
    print(f"Files:  {len(files)}")
    print(f"Size:   {size_mb:.2f} MB")

if __name__ == "__main__":
    main()