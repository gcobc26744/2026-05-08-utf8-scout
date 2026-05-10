# UTF-8 Scout

## What it is
`utf8_scout.py` is a tiny CLI that scans a folder for text files and reports which ones fail to decode as UTF-8 (a common cause of mojibake/garbled output in terminals).

## Why it exists
I often hit “file looks fine in GitHub/VS Code but looks garbled in Terminal/PowerShell”. This project helps me quickly:
- confirm whether a file is actually UTF-8
- identify files that are likely Big5/CP950 (or other legacy encodings)
- optionally convert them to UTF-8 safely (with backups)

## How to run
Requirements: Python 3.10+

```bash
cd projects/2026-05-08-utf8-scout
python src/utf8_scout.py . --include **/*.md **/*.py **/*.txt
```

## Examples

Scan a project folder:

```bash
python src/utf8_scout.py ..\\2026-05-04-csv-buddy --include **/*.md **/*.py
```

Print a quick breakdown by extension:

```bash
python src/utf8_scout.py ..\\2026-05-04-csv-buddy --include **/*.md **/*.py --summary
```

Write a JSON report to a file (or use `-` for stdout):

```bash
python src/utf8_scout.py ..\\2026-05-04-csv-buddy --include **/*.md --report-json report.json
```

Attempt safe conversion (creates `.bak` files first):

```bash
python src/utf8_scout.py ..\\2026-05-04-csv-buddy --include **/*.md --fix --from cp950 big5
```

## Next steps
- [ ] Detect BOM / UTF-16 files explicitly
- [ ] Add an option to auto-suggest likely source encoding
