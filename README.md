# filter-bib

A small script that strips `.bib` files down to only the entries actually
cited in a LaTeX paper. Useful when you're working from a giant shared
bibliography (e.g. the [ACL Anthology](https://aclanthology.org/) `.bib`
shards, which run tens of thousands of entries) but your paper only cites a
handful of them.

It scans your `.tex` file for `\cite`, `\citet`, `\citep`, `\citealt`, and
other natbib/biblatex-style citation commands — including comma-separated
multi-key citations like `\cite{key1, key2}` and optional `[..]` arguments —
then rewrites each `.bib` file you give it to keep only the matching entries
(plus any `@string{...}` declarations, which are always kept since other
entries may depend on them).

By default it also follows `\input{...}`/`\include{...}` directives,
recursively, so citations that live in a separately included file (a
`tables/`, `figures/`, or per-section `.tex` file) aren't missed just
because you only pointed it at your main file. Commented-out lines are
ignored too, so a `\cite` left inside a `%` comment won't keep an entry you
don't actually use.

No third-party dependencies. Requires Python 3.7+.

## Usage

```bash
python3 filter_bib.py --tex paper.tex --bib references.bib
```

You can pass more than one file to either flag. Every `--tex` file (plus
anything it `\input`s/`\include`s) is scanned for citation keys; every
`--bib` file is filtered independently against that combined set of keys:

```bash
python3 filter_bib.py --tex paper.tex --bib refs1.bib refs2.bib refs3.bib

# Point it at extra .tex files explicitly too, if you want
python3 filter_bib.py --tex paper.tex tables/extra.tex --bib references.bib
```

### Options

- `--dry-run` — report what would change without writing anything.
- `--no-backup` — skip saving a backup before overwriting each `.bib` file.
- `--no-follow-inputs` — scan only the file(s) passed to `--tex`, without
  following `\input`/`\include`.
- `--root-dir DIR` — directory `\input`/`\include` paths are resolved
  against (defaults to the directory of the first `--tex` file, matching
  how LaTeX itself resolves them).

```bash
# Preview the result first
python3 filter_bib.py --dry-run --tex paper.tex --bib references.bib

# Then actually run it
python3 filter_bib.py --tex paper.tex --bib references.bib
```

## What it does

- Reads each `--tex` file, follows its `\input`/`\include` chain, and
  collects every citation key referenced anywhere via `\cite...{...}`
  (ignoring commented-out lines).
- For each `--bib` file, keeps only the entries whose key was cited (plus
  `@string` declarations), and removes the rest.
- Overwrites each `.bib` file in place. Before doing so, it saves the
  original alongside it as `<name>.orig.bib` — unless that backup already
  exists (so re-running the script is safe and won't clobber your real
  original) or `--no-backup` is passed.
- At the end, it prints any cited keys that weren't found in any of the
  given `.bib` files — that usually means they live in a different
  bibliography file you didn't pass in, or there's a typo in the citation
  key. The script exits with status 1 in that case.

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
anthology-1.bib: 85933 entries -> would keep 47 (removed 85886)
anthology-2.bib: 36206 entries -> would keep 7 (removed 36199)

100 cited key(s) not found in any given .bib file (check other bibliography files, or for typos):
  - mikolov2013distributed
  - ...
```

Note `acl_latex.tex` pulled in `tables/DS.tex` automatically via `\input` —
no need to list it separately.

## License

MIT — see [LICENSE](LICENSE).
