from __future__ import annotations

import argparse
import fnmatch
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_INCLUDE = ["**/*.md", "**/*.txt", "**/*.py", "**/*.json", "**/*.yml", "**/*.yaml"]
DEFAULT_EXCLUDE_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}


@dataclass(frozen=True)
class ScanResult:
    path: Path
    ok_utf8: bool | None
    error: str | None


def _ext_key(path: Path) -> str:
    ext = path.suffix.lower()
    return ext if ext else "(no ext)"


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


def _is_probably_binary(data: bytes, *, sample_size: int = 4096, nontext_threshold: float = 0.30) -> bool:
    sample = data[:sample_size]
    if not sample:
        return False
    if b"\x00" in sample:
        return True

    nontext = 0
    for b in sample:
        # treat common whitespace and printable ASCII as text; count C0 controls + DEL as non-text
        if b in (9, 10, 13) or 32 <= b <= 126 or b >= 128:
            continue
        nontext += 1

    return (nontext / len(sample)) > nontext_threshold


def scan_utf8(
    root: Path,
    include: list[str],
    exclude: list[str],
    exclude_dirs: set[str],
    *,
    skip_binary: bool = False,
) -> list[ScanResult]:
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

        if skip_binary and _is_probably_binary(data):
            results.append(ScanResult(path=file_path, ok_utf8=None, error="skipped (looks like binary)"))
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


def guess_encodings(path: Path, candidate_encodings: list[str]) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    guesses: list[dict[str, Any]] = []

    for enc in candidate_encodings:
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue

        first_line = ""
        for line in text.splitlines():
            if line.strip():
                first_line = line.strip()
                break

        guesses.append({"encoding": enc, "first_line": first_line})

    return guesses


def _write_report_json(report_path: str, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if report_path == "-":
        print(text, end="")
        return
    Path(report_path).write_text(text, encoding="utf-8", newline="\n")


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
    parser.add_argument(
        "--guess",
        action="store_true",
        help="For non-UTF-8 files, try decoding with --from encodings and print suggestions (no changes made).",
    )
    parser.add_argument("--no-backup", action="store_true", help="Do not write .bak backups when converting.")
    parser.add_argument(
        "--skip-binary",
        action="store_true",
        help="Skip files that look like binary data (heuristic). Useful when scanning with broad include patterns.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a per-extension summary table (total/ok/bad/skipped).",
    )
    parser.add_argument(
        "--report-json",
        default=None,
        help="Write a JSON report to this path, or '-' for stdout.",
    )

    args = parser.parse_args()
    root = Path(args.root).resolve()
    include = args.include if args.include is not None else DEFAULT_INCLUDE
    exclude_dirs = set(args.exclude_dir)

    results = scan_utf8(
        root=root,
        include=include,
        exclude=args.exclude,
        exclude_dirs=exclude_dirs,
        skip_binary=args.skip_binary,
    )
    skipped = [r for r in results if r.ok_utf8 is None]
    checked = [r for r in results if r.ok_utf8 is not None]
    bad = [r for r in checked if r.ok_utf8 is False]

    print(f"Scanned: {len(results)} files")
    print(f"UTF-8 OK: {len([r for r in checked if r.ok_utf8 is True])}")
    print(f"Not UTF-8: {len(bad)}")
    if skipped:
        print(f"Skipped (binary): {len(skipped)}")

    if args.summary:
        summary: dict[str, dict[str, int]] = {}
        for r in results:
            ext = _ext_key(r.path)
            bucket = summary.setdefault(ext, {"total": 0, "ok": 0, "bad": 0, "skipped": 0})
            bucket["total"] += 1
            if r.ok_utf8 is None:
                bucket["skipped"] += 1
            elif r.ok_utf8:
                bucket["ok"] += 1
            else:
                bucket["bad"] += 1

        print("\nBy extension:")
        print("ext\t total\t ok\t bad\t skipped")
        for ext in sorted(summary.keys()):
            b = summary[ext]
            print(f"{ext}\t {b['total']}\t {b['ok']}\t {b['bad']}\t {b['skipped']}")

    if not bad:
        if args.report_json:
            _write_report_json(
                args.report_json,
                {
                    "root": str(root),
                    "scanned": len(results),
                    "ok_utf8": len([r for r in checked if r.ok_utf8 is True]),
                    "not_utf8": len(bad),
                    "skipped_binary": len(skipped),
                    "include": include,
                    "exclude": args.exclude,
                    "exclude_dirs": sorted(exclude_dirs),
                    "skip_binary": args.skip_binary,
                    "files": [],
                    "converted": {"attempted": 0, "ok": 0, "failed": 0, "from_encodings": args.from_encodings},
                },
            )
        return 0

    print("\nNon-UTF-8 files:")
    for r in bad:
        rel = r.path.relative_to(root)
        print(f"- {rel} ({r.error})")

    guesses_by_file: dict[str, list[dict[str, Any]]] = {}
    if args.guess:
        print("\nEncoding guesses (from --from list):")
        for r in bad:
            rel = str(r.path.relative_to(root))
            guesses = guess_encodings(r.path, candidate_encodings=args.from_encodings)
            guesses_by_file[rel] = guesses
            if not guesses:
                print(f"- {rel}: (no candidates decoded cleanly)")
                continue
            best = guesses[0]
            preview = best["first_line"]
            if preview and len(preview) > 80:
                preview = preview[:80] + "…"
            if preview:
                print(f"- {rel}: {best['encoding']} (first line: {preview})")
            else:
                print(f"- {rel}: {best['encoding']}")

    if not args.fix:
        if args.report_json:
            payload: dict[str, Any] = {
                "root": str(root),
                "scanned": len(results),
                "ok_utf8": len([r for r in checked if r.ok_utf8 is True]),
                "not_utf8": len(bad),
                "skipped_binary": len(skipped),
                "include": include,
                "exclude": args.exclude,
                "exclude_dirs": sorted(exclude_dirs),
                "skip_binary": args.skip_binary,
                "files": [{"path": str(r.path.relative_to(root)), "error": r.error} for r in bad],
                "skipped_files": [{"path": str(r.path.relative_to(root)), "reason": r.error} for r in skipped],
                "converted": {"attempted": 0, "ok": 0, "failed": 0, "from_encodings": args.from_encodings},
            }
            if args.guess:
                payload["guesses"] = guesses_by_file
            _write_report_json(
                args.report_json,
                payload,
            )
        return 2

    print("\nConverting:")
    converted = 0
    conversion_results: list[dict[str, Any]] = []
    for r in bad:
        ok, msg = try_convert_to_utf8(
            r.path, from_encodings=args.from_encodings, make_backup=(not args.no_backup)
        )
        rel = r.path.relative_to(root)
        print(f"- {rel}: {msg}")
        conversion_results.append({"path": str(rel), "ok": ok, "message": msg})
        if ok:
            converted += 1

    print(f"\nConverted: {converted}/{len(bad)}")

    if args.report_json:
        _write_report_json(
            args.report_json,
            {
                "root": str(root),
                "scanned": len(results),
                "ok_utf8": len([r for r in checked if r.ok_utf8 is True]),
                "not_utf8": len(bad),
                "skipped_binary": len(skipped),
                "include": include,
                "exclude": args.exclude,
                "exclude_dirs": sorted(exclude_dirs),
                "skip_binary": args.skip_binary,
                "files": [{"path": str(r.path.relative_to(root)), "error": r.error} for r in bad],
                "skipped_files": [{"path": str(r.path.relative_to(root)), "reason": r.error} for r in skipped],
                "converted": {
                    "attempted": len(bad),
                    "ok": converted,
                    "failed": len(bad) - converted,
                    "from_encodings": args.from_encodings,
                    "results": conversion_results,
                },
            },
        )

    return 0 if converted == len(bad) else 3


if __name__ == "__main__":
    raise SystemExit(main())
