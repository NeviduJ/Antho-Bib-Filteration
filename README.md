# filter-bib

A small script that strips a `.bib` file down to only the entries actually
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

No third-party dependencies. Requires Python 3.7+.

## Usage

```bash
python3 filter_bib.py paper.tex references.bib
```

You can pass more than one `.bib` file — each one is filtered independently
against the same set of citation keys found in the `.tex` file:

```bash
python3 filter_bib.py paper.tex refs1.bib refs2.bib refs3.bib
```

### Options

- `--dry-run` — report what would change without writing anything.
- `--no-backup` — skip saving a backup before overwriting each `.bib` file.

```bash
# Preview the result first
python3 filter_bib.py --dry-run paper.tex references.bib

# Then actually run it
python3 filter_bib.py paper.tex references.bib
```

## What it does

- Reads `paper.tex` and collects every citation key referenced anywhere via
  `\cite...{...}`.
- For each `.bib` file passed in, keeps only the entries whose key was
  cited (plus `@string` declarations), and removes the rest.
- Overwrites each `.bib` file in place. Before doing so, it saves the
  original alongside it as `<name>.orig.bib` — unless that backup already
  exists (so re-running the script is safe and won't clobber your real
  original) or `--no-backup` is passed.
- At the end, it prints any cited keys that weren't found in any of the
  given `.bib` files — that usually means they live in a different
  bibliography file, or there's a typo in the citation key.

Entries are located with a brace-matching scan rather than naive
line-splitting, so it correctly handles the rare entry whose fields happen
to span multiple physical lines or contain a literal `@` character in a
title or abstract.

## Example

```bash
$ python3 filter_bib.py --dry-run acl_latex.tex anthology-1.bib anthology-2.bib
Found 50 unique citation key(s) in acl_latex.tex
anthology-1.bib: 85933 entries -> would keep 24 (removed 85909)
anthology-2.bib: 36206 entries -> would keep 3 (removed 36203)

25 cited key(s) not found in any given .bib file (check other bibliography files, or for typos):
  - mikolov2013distributed
  - ...
```

## License

MIT — see [LICENSE](LICENSE).
