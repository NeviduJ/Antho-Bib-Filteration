# anthology-bib-filter

The [ACL Anthology](https://aclanthology.org/) bibliography (`anthology-1.bib`,
`anthology-2.bib`, ...) runs 50MB+ and tens of thousands of entries — but
your paper probably only cites a handful of them. This script trims those
files down to just the entries you actually cite, and removes any
duplicate references along the way.

No install, no dependencies — just Python 3.

## Quick start

1. Download [`filter_bib.py`](filter_bib.py) into your paper's folder (next
   to your `.tex` and `.bib` files).
2. Run:

```bash
python3 filter_bib.py --tex your_paper.tex --bib anthology-1.bib anthology-2.bib
```

That's it. It scans `your_paper.tex` for every `\cite`/`\citet`/`\citep`
key, and rewrites `anthology-1.bib`/`anthology-2.bib` in place to keep only
those entries.

Not sure what it'll change? Add `--dry-run` first — it prints a report
without touching any file:

```bash
python3 filter_bib.py --dry-run --tex your_paper.tex --bib anthology-1.bib anthology-2.bib
```

### Example output

```
Found 154 unique citation key(s) across 2 file(s)
anthology-1.bib: 85933 entries -> kept 48 (removed 85885)
anthology-2.bib: 36206 entries -> kept 7 (removed 36199)

All cited keys were found and kept.
```

## Good to know

- It automatically picks up any file your `.tex` pulls in via
  `\input{...}`/`\include{...}` (e.g. a `tables/` or `figures/` file), so
  you only need to point it at your main `.tex` file.
- It also reads your `\bibliography{...}` line to find every other `.bib`
  file the paper uses (like `custom.bib`), and removes any citation key
  that's duplicated across those files, keeping one copy.
- No backup is made by default — pass `--backup` if you want a
  `<name>.orig.bib` copy saved before each file is overwritten.
- Uses biblatex (`\addbibresource{...}`) instead of classic
  `\bibliography{...}`? List every `.bib` file explicitly after `--bib`
  instead of relying on auto-discovery.

## All options

| Flag | What it does |
|---|---|
| `--tex FILE [FILE ...]` | Your `.tex` file(s) to scan for citations (required) |
| `--bib FILE [FILE ...]` | `.bib` file(s) to trim down to cited entries (required) |
| `--dry-run` | Preview changes without writing anything |
| `--backup` | Save a `.orig.bib` backup before overwriting a file |
| `--no-dedupe` | Skip the `\bibliography{...}` lookup and duplicate removal |
| `--no-follow-inputs` | Don't follow `\input`/`\include`; scan only the given `--tex` file(s) |
| `--root-dir DIR` | Where to resolve `\input`/`\bibliography` paths from (default: your `--tex` file's folder) |

## License

MIT — see [LICENSE](LICENSE).
