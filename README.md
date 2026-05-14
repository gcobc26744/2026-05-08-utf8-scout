# UTF-8 Scout

## What it is
`utf8_scout.py` is a tiny CLI that scans a folder for text files and reports which ones fail to decode as UTF-8 (a common cause of mojibake/garbled output in terminals).

## Why it exists
I often hit: "file looks fine in GitHub/VS Code but looks garbled in Terminal/PowerShell". This project helps me quickly:
- confirm whether a file is actually UTF-8
- identify files that are likely Big5/CP950 (or other legacy encodings)
- optionally convert them to UTF-8 safely (with backups)

## How to run
Requirements: Python 3.10+

### Option A: run from source

```bash
cd projects/2026-05-08-utf8-scout
python src/utf8_scout.py . --include **/*.md **/*.py **/*.txt
```

### Option B: install the CLI (editable)

```bash
cd projects/2026-05-08-utf8-scout
python -m pip install -e .
utf8-scout . --include **/*.md **/*.py **/*.txt
```

## Examples

Scan a project folder:

```bash
python src/utf8_scout.py ..\\2026-05-04-csv-buddy --include **/*.md **/*.py
```

Skip files that look like binary data (helpful if you include broad patterns):

```bash
python src/utf8_scout.py ..\\2026-05-04-csv-buddy --include **/* --skip-binary
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

Try to guess the source encoding (no changes made):

```bash
python src/utf8_scout.py ..\\2026-05-04-csv-buddy --include **/*.md --guess --from cp950 big5 cp936 shift_jis
```

## Next steps
- [ ] Detect BOM / UTF-16 files explicitly
- [ ] Improve encoding guessing (confidence scoring)
