from __future__ import annotations

import argparse
import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_INCLUDE = ["**/*.md", "**/*.txt", "**/*.py", "**/*.json", "**/*.yml", "**/*.yaml"]
DEFAULT_EXCLUDE_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}


@dataclass(frozen=True)
class ScanResult:
    path: Path
    ok_utf8: bool
    error: str | None


def _iter_files(root: Path, exclude_dirs: set[str]) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for name in filenames:
            files.append(Path(dirpath) / name)
    return files


def _matches_any(path: Path, patterns: list[str]) -> bool:
    p = path.as_posix()
    for pat in patterns:
        if fnmatch.fnmatch(p, pat):
            return True
        # Common expectation: "**/*.md" should also match "README.md" at the root.
        if pat.startswith("**/") and fnmatch.fnmatch(p, pat[3:]):
            return True
    return False


def scan_utf8(root: Path, include: list[str], exclude: list[str], exclude_dirs: set[str]) -> list[ScanResult]:
    results: list[ScanResult] = []
    candidates = _iter_files(root, exclude_dirs=exclude_dirs)

    for file_path in candidates:
        rel = file_path.relative_to(root)
        rel_posix = rel.as_posix()

        if include and not _matches_any(rel, include):
            continue
        if exclude and any(fnmatch.fnmatch(rel_posix, pat) for pat in exclude):
            continue

        try:
            data = file_path.read_bytes()
        except OSError as e:
            results.append(ScanResult(path=file_path, ok_utf8=False, error=f"read error: {e}"))
            continue

        try:
            data.decode("utf-8")
            results.append(ScanResult(path=file_path, ok_utf8=True, error=None))
        except UnicodeDecodeError as e:
            results.append(ScanResult(path=file_path, ok_utf8=False, error=f"utf-8 decode error: {e}"))

    return results


def try_convert_to_utf8(path: Path, from_encodings: list[str], make_backup: bool) -> tuple[bool, str]:
    raw = path.read_bytes()
    last_error: str | None = None

    for enc in from_encodings:
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError as e:
            last_error = f"{enc}: {e}"
            continue

        if make_backup:
            backup = path.with_suffix(path.suffix + ".bak")
            if not backup.exists():
                backup.write_bytes(raw)

        path.write_text(text, encoding="utf-8", newline="\n")
        return True, f"converted using {enc}"

    if last_error is None:
        last_error = "no encodings attempted"
    return False, f"failed to convert ({last_error})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan for files that are not valid UTF-8 and optionally convert them.")
    parser.add_argument("root", nargs="?", default=".", help="Root folder to scan (default: .)")
    parser.add_argument(
        "--include",
        nargs="*",
        default=None,
        help=f"Glob patterns (relative) to include. Default: {' '.join(DEFAULT_INCLUDE)}",
    )
    parser.add_argument("--exclude", nargs="*", default=[], help="Glob patterns (relative) to exclude.")
    parser.add_argument(
        "--exclude-dir",
        nargs="*",
        default=sorted(DEFAULT_EXCLUDE_DIRS),
        help="Directory names to skip during traversal.",
    )
    parser.add_argument("--fix", action="store_true", help="Attempt to convert non-UTF-8 files to UTF-8.")
    parser.add_argument(
        "--from",
        dest="from_encodings",
        nargs="*",
        default=["cp950", "big5", "cp936", "shift_jis"],
        help="Encodings to try when converting (default: cp950 big5 cp936 shift_jis).",
    )
    parser.add_argument("--no-backup", action="store_true", help="Do not write .bak backups when converting.")

    args = parser.parse_args()
    root = Path(args.root).resolve()
    include = args.include if args.include is not None else DEFAULT_INCLUDE
    exclude_dirs = set(args.exclude_dir)

    results = scan_utf8(root=root, include=include, exclude=args.exclude, exclude_dirs=exclude_dirs)
    bad = [r for r in results if not r.ok_utf8]

    print(f"Scanned: {len(results)} files")
    print(f"UTF-8 OK: {len(results) - len(bad)}")
    print(f"Not UTF-8: {len(bad)}")

    if not bad:
        return 0

    print("\nNon-UTF-8 files:")
    for r in bad:
        rel = r.path.relative_to(root)
        print(f"- {rel} ({r.error})")

    if not args.fix:
        return 2

    print("\nConverting:")
    converted = 0
    for r in bad:
        ok, msg = try_convert_to_utf8(
            r.path, from_encodings=args.from_encodings, make_backup=(not args.no_backup)
        )
        rel = r.path.relative_to(root)
        print(f"- {rel}: {msg}")
        if ok:
            converted += 1

    print(f"\nConverted: {converted}/{len(bad)}")
    return 0 if converted == len(bad) else 3


if __name__ == "__main__":
    raise SystemExit(main())
