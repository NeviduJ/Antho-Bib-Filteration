# filter-bib

A small script that strips `.bib` files down to only the entries actually
cited in a LaTeX paper, and removes duplicate entries across every
bibliography file the paper uses. Useful when you're working from a giant
shared bibliography (e.g. the [ACL Anthology](https://aclanthology.org/)
`.bib` shards, which run tens of thousands of entries) but your paper only
cites a handful of them.

It scans your `.tex` file for `\cite`, `\citet`, `\citep`, `\citealt`, and
other natbib/biblatex-style citation commands — including comma-separated
multi-key citations like `\cite{key1, key2}` and optional `[..]` arguments —
then rewrites each **primary** `.bib` file (the ones you pass to `--bib`) to
keep only the matching entries (plus any `@string{...}` declarations, which
are always kept since other entries may depend on them).

By default it also follows `\input{...}`/`\include{...}` directives,
recursively, so citations that live in a separately included file (a
`tables/`, `figures/`, or per-section `.tex` file) aren't missed just
because you only pointed it at your main file. Commented-out lines are
ignored too, so a `\cite` left inside a `%` comment won't keep an entry you
don't actually use.

**Deduplication:** the script also looks for a `\bibliography{...}` command
in your `.tex` file(s) to find every `.bib` file the paper actually draws
from — e.g. `\bibliography{anthology-1, anthology-2, custom}` resolves to
`anthology-1.bib`, `anthology-2.bib`, `custom.bib` — in the order BibTeX
itself would resolve them. If the same citation key is defined in more than
one of those files, only the copy in the file listed *first* is kept; the
duplicate is removed from every later file, whether or not that file is one
of the `--bib` primaries. Files outside this discovered set are left alone
unless you pass them to `--bib` explicitly.

> **Using biblatex instead of BibTeX?** Auto-discovery only understands the
> classic `\bibliography{...}` command. If your project uses biblatex's
> `\addbibresource{...}` (typically with `\usepackage{biblatex}`), pass every
> `.bib` file explicitly to `--bib` instead of relying on discovery — see
> [Manually listing bib files](#manually-listing-bib-files-biblatex-or-otherwise)
> below.

No third-party dependencies. Requires Python 3.7+.

## Usage

```bash
python3 filter_bib.py --tex paper.tex --bib references.bib
```

You can pass more than one file to either flag. Every `--tex` file (plus
anything it `\input`s/`\include`s) is scanned for citation keys; every
`--bib` file is trimmed to that combined set of keys:

```bash
python3 filter_bib.py --tex paper.tex --bib anthology-1.bib anthology-2.bib

# Point it at extra .tex files explicitly too, if you want
python3 filter_bib.py --tex paper.tex tables/extra.tex --bib references.bib
```

### Manually listing bib files (biblatex or otherwise)

If your project uses biblatex's `\addbibresource{...}` rather than
`\bibliography{...}`, auto-discovery won't find your bib files — pass every
one of them to `--bib` explicitly instead:

```bash
python3 filter_bib.py --tex paper.tex \
  --bib references.bib extra-refs.bib
```

Every file passed to `--bib` is treated as primary: each is trimmed down to
cited-only entries, and duplicate keys across the whole set you listed are
removed (keeping the copy in whichever file you passed first). There's
currently no way to include a file for deduplication *without* also
trimming it unless it's picked up via `\bibliography{...}` discovery — so
in biblatex/manual mode, only pass files you're happy to have trimmed.

### Options

- `--dry-run` — report what would change without writing anything.
- `--backup` — save a `<name>.orig.bib` backup before overwriting a `.bib`
  file (off by default).
- `--no-follow-inputs` — scan only the file(s) passed to `--tex`, without
  following `\input`/`\include`.
- `--no-dedupe` — don't look for `\bibliography{...}` or remove duplicate
  keys across files; only trim the `--bib` files given.
- `--root-dir DIR` — directory `\input`/`\include`/`\bibliography` paths are
  resolved against (defaults to the directory of the first `--tex` file,
  matching how LaTeX itself resolves them).

```bash
# Preview the result first
python3 filter_bib.py --dry-run --tex paper.tex --bib references.bib

# Then actually run it
python3 filter_bib.py --tex paper.tex --bib references.bib
```

## What it does

1. Reads each `--tex` file, follows its `\input`/`\include` chain, and
   collects every citation key referenced anywhere via `\cite...{...}`
   (ignoring commented-out lines).
2. Reads the `\bibliography{...}` command to find every `.bib` file the
   paper references, in order.
3. Trims each **primary** (`--bib`) file down to only the entries whose key
   was cited (plus `@string` declarations).
4. Scans the full set of referenced `.bib` files for keys defined in more
   than one file, and removes the duplicate from every file after the
   first one that defines it — including non-primary files, if that's
   where the duplicate lives.
5. Writes back: primary files are always (re)written; non-primary files are
   only touched if a duplicate was actually removed from them. No backup is
   made unless you pass `--backup`, in which case each file written to gets
   a `<name>.orig.bib` copy first (skipped if that backup already exists).
6. Reports any cited key that wasn't found in *any* scanned `.bib` file —
   that usually means a typo in the key, and the script exits with status 1
   in that case.

Entries are located with a brace-matching scan rather than naive
line-splitting, so it correctly handles the rare entry whose fields happen
to span multiple physical lines or contain a literal `@` character in a
title or abstract.

## Example

```bash
$ python3 filter_bib.py --dry-run --tex acl_latex.tex --bib anthology-1.bib anthology-2.bib
Scanning:
  - acl_latex.tex
  - tables/DS.tex

Found 152 unique citation key(s) across 2 file(s)

Bibliography files referenced by \bibliography{...}:
  - anthology-1.bib (primary)
  - anthology-2.bib (primary)
  - custom.bib
  - lrec2026-example.bib
anthology-1.bib: 47 entries -> would keep 47 (removed 0)
anthology-2.bib: 7 entries -> would keep 7 (removed 0)
lrec2026-example.bib (dedupe only): 74 entries -> would keep 73 (removed 1)

Removed 1 duplicate key(s) (kept the copy in the first-listed file):
  - fernando1949palaeographical: removed from lrec2026-example.bib, kept in custom.bib

All cited keys were found and kept.
```

`acl_latex.tex` pulled in `tables/DS.tex` automatically via `\input`, and
`custom.bib`/`lrec2026-example.bib` were picked up automatically from
`\bibliography{...}` for deduplication — no need to list either by hand.

## License

MIT — see [LICENSE](LICENSE).
