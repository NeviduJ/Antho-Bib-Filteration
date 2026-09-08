#!/usr/bin/env python3
"""
filter_bib.py — strip .bib files down to only the entries actually cited
in a LaTeX document (and anything it \\input's or \\include's), and remove
duplicate entries across the full set of bibliographies the paper uses.

Scans your .tex file(s) for \\cite, \\citet, \\citep, \\citealt, and similar
natbib/biblatex citation commands (including comma-separated multi-key
citations and optional [..] arguments), then rewrites each "primary" .bib
file (the ones you pass to --bib) to keep only the matching entries (plus
any @string{...} declarations, which are always kept since other entries
may depend on them).

By default it also follows \\input{...}/\\include{...} directives found in
each given .tex file, recursively, so citations hiding in a separately
\\input'ed tables/figures/sections file are not missed. Commented-out
LaTeX lines (text after an unescaped %) are ignored.

Deduplication: the script looks for a \\bibliography{...} command in your
.tex file(s) to find every .bib file the paper actually draws from (e.g.
`\\bibliography{anthology-1, anthology-2, custom}` -> anthology-1.bib,
anthology-2.bib, custom.bib), in the order BibTeX itself would resolve
them. If the same citation key is defined in more than one of those files,
only the copy in the file listed first is kept; the duplicate entry is
removed from every later file (whether or not that file is one of the
--bib "primary" files). Files outside this discovered set are left alone
unless you pass them explicitly to --bib.

Entries are located with a brace-matching scan rather than naive
line-splitting, so it correctly handles entries whose field values happen
to span multiple physical lines or contain literal '@' characters.

Usage:
    python3 filter_bib.py --tex paper.tex --bib references.bib
    python3 filter_bib.py --tex paper.tex --bib anthology-1.bib anthology-2.bib
    python3 filter_bib.py --dry-run --tex paper.tex --bib references.bib
    python3 filter_bib.py --backup --tex paper.tex --bib references.bib
    python3 filter_bib.py --no-dedupe --tex paper.tex --bib references.bib

Files are overwritten in place with no backup by default. Pass --backup to
save a copy of each file this script writes to, next to it, as
"<name>.orig.bib" (skipped if that backup already exists, so re-running
with --backup never clobbers a backup from an earlier run).

Requires Python 3.7+. No third-party dependencies.
"""
import argparse
import re
import sys
from pathlib import Path

CITE_RE = re.compile(r'\\[A-Za-z]*[Cc]ite[A-Za-z]*\*?(?:\s*\[[^\]]*\])*\{([^}]*)\}')
INPUT_RE = re.compile(r'\\(?:input|include)\{([^}]+)\}')
BIBLIOGRAPHY_RE = re.compile(r'\\bibliography\{([^}]*)\}')
ENTRY_START_RE = re.compile(r'@(\w+)\{')
KEY_RE = re.compile(r'@\w+\{\s*([^,\s}]+)\s*[,}]')


def strip_comments(text: str) -> str:
    """Remove LaTeX line comments (unescaped % to end of line)."""
    out_lines = []
    for line in text.split("\n"):
        chunk = []
        i = 0
        n = len(line)
        while i < n:
            ch = line[i]
            if ch == "\\" and i + 1 < n:
                chunk.append(line[i:i + 2])
                i += 2
                continue
            if ch == "%":
                break
            chunk.append(ch)
            i += 1
        out_lines.append("".join(chunk))
    return "\n".join(out_lines)


def discover_tex_files(entry_files, root_dir: Path, follow_inputs: bool):
    """Resolve entry .tex files, optionally following \\input/\\include recursively."""
    seen = set()
    ordered = []
    queue = list(entry_files)

    while queue:
        f = queue.pop(0)
        rf = f.resolve()
        if rf in seen:
            continue
        seen.add(rf)
        if not rf.exists():
            print(f"warning: could not find {f} (looked for {rf}), skipping", file=sys.stderr)
            continue
        ordered.append(rf)

        if not follow_inputs:
            continue
        text = strip_comments(rf.read_text(encoding="utf-8", errors="replace"))
        for m in INPUT_RE.finditer(text):
            inc = m.group(1).strip()
            if not inc.lower().endswith(".tex"):
                inc += ".tex"
            queue.append(root_dir / inc)

    return ordered


def extract_used_keys(tex_files) -> set:
    keys = set()
    for tex_path in tex_files:
        text = strip_comments(tex_path.read_text(encoding="utf-8", errors="replace"))
        for match in CITE_RE.finditer(text):
            for key in match.group(1).split(","):
                key = key.strip()
                if key:
                    keys.add(key)
    return keys


def discover_bibliography_files(tex_files, root_dir: Path):
    """Find every .bib file referenced via \\bibliography{...}, in order, deduplicated."""
    names = []
    for tex_path in tex_files:
        text = strip_comments(tex_path.read_text(encoding="utf-8", errors="replace"))
        for m in BIBLIOGRAPHY_RE.finditer(text):
            for name in m.group(1).split(","):
                name = name.strip()
                if name and name not in names:
                    names.append(name)

    resolved = []
    for name in names:
        p = Path(name)
        if not p.suffix:
            p = p.with_suffix(".bib")
        if not p.is_absolute():
            p = root_dir / p
        resolved.append(p)
    return resolved


def parse_entries(text: str):
    """Yield ('raw', text) for inter-entry text and ('entry', type, key, text) for entries."""
    pos = 0
    while True:
        m = ENTRY_START_RE.search(text, pos)
        if not m:
            yield ("raw", text[pos:])
            return
        if m.start() > pos:
            yield ("raw", text[pos:m.start()])

        entry_type = m.group(1)
        j = m.end()  # position right after the opening '{'
        depth = 1
        while depth > 0:
            next_open = text.find("{", j)
            next_close = text.find("}", j)
            if next_close == -1:
                raise ValueError(f"Unbalanced braces starting near offset {m.start()}")
            if next_open != -1 and next_open < next_close:
                depth += 1
                j = next_open + 1
            else:
                depth -= 1
                j = next_close + 1
        entry_end = j
        entry_text = text[m.start():entry_end]
        key_match = KEY_RE.match(entry_text)
        key = key_match.group(1) if key_match else None
        yield ("entry", entry_type, key, entry_text)
        pos = entry_end


def load_bib(bib_path: Path):
    """Parse a .bib file into a list of items, each either ('raw', text) or
    a mutable dict {'type', 'key', 'text', 'keep'} for an entry."""
    text = bib_path.read_text(encoding="utf-8", errors="replace")
    items = []
    for item in parse_entries(text):
        if item[0] == "raw":
            items.append(("raw", item[1]))
        else:
            _, entry_type, key, entry_text = item
            items.append({"type": entry_type, "key": key, "text": entry_text, "keep": True})
    return items


def render_bib(items) -> str:
    parts = []
    for item in items:
        if isinstance(item, tuple):
            parts.append(item[1])
        elif item["keep"]:
            parts.append(item["text"])
    return "".join(parts)


def write_bib(bib_path: Path, items, make_backup: bool):
    if make_backup:
        backup_path = bib_path.with_suffix(".orig.bib")
        if not backup_path.exists():
            backup_path.write_bytes(bib_path.read_bytes())
    bib_path.write_text(render_bib(items), encoding="utf-8")


def entry_items(items):
    for item in items:
        if isinstance(item, dict):
            yield item


def main():
    parser = argparse.ArgumentParser(
        description="Strip .bib files down to only the entries cited in a LaTeX document, "
                     "and remove duplicate keys across every bib file the paper references.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--tex", type=Path, nargs="+", required=True, dest="tex_files",
                         help="LaTeX file(s) to scan for \\cite/\\citet/... commands "
                              "and for \\bibliography{...}")
    parser.add_argument("--bib", type=Path, nargs="+", required=True, dest="bib_files",
                         help="Primary .bib file(s) to trim down to only cited entries")
    parser.add_argument("--root-dir", type=Path, default=None,
                         help="Directory that \\input/\\include/\\bibliography paths are "
                              "resolved relative to (default: directory of the first --tex file)")
    parser.add_argument("--no-follow-inputs", action="store_true",
                         help="Don't follow \\input{...}/\\include{...} directives; "
                              "scan only the file(s) passed to --tex")
    parser.add_argument("--no-dedupe", action="store_true",
                         help="Don't look for \\bibliography{...} or remove duplicate keys "
                              "across bib files; only trim the --bib files given")
    parser.add_argument("--backup", action="store_true",
                         help="Save a .orig.bib backup before overwriting a .bib file "
                              "(off by default)")
    parser.add_argument("--dry-run", action="store_true",
                         help="Report what would change without writing anything")
    args = parser.parse_args()

    for tex_path in args.tex_files:
        if not tex_path.exists():
            parser.error(f"tex file not found: {tex_path}")
    for bib_path in args.bib_files:
        if not bib_path.exists():
            parser.error(f"bib file not found: {bib_path}")

    root_dir = args.root_dir if args.root_dir else args.tex_files[0].resolve().parent

    tex_files = discover_tex_files(args.tex_files, root_dir, follow_inputs=not args.no_follow_inputs)
    print("Scanning:")
    for f in tex_files:
        print(f"  - {f}")

    used_keys = extract_used_keys(tex_files)
    print(f"\nFound {len(used_keys)} unique citation key(s) across {len(tex_files)} file(s)")

    primary_paths = [p.resolve() for p in args.bib_files]

    # Build the ordered universe of bib files: everything \bibliography{} references,
    # with any --bib file not already in that list appended (so it's still processed).
    if args.no_dedupe:
        universe_paths = list(primary_paths)
    else:
        discovered = discover_bibliography_files(tex_files, root_dir)
        universe_paths = []
        seen = set()
        for p in discovered:
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                universe_paths.append(rp)
        for rp in primary_paths:
            if rp not in seen:
                seen.add(rp)
                universe_paths.append(rp)
        if discovered:
            print("\nBibliography files referenced by \\bibliography{...}:")
            for p in universe_paths:
                tag = " (primary)" if p in primary_paths else ""
                exists = "" if p.exists() else "  [not found, skipping]"
                print(f"  - {p}{tag}{exists}")
        universe_paths = [p for p in universe_paths if p.exists()]

    # Load every file in the universe once.
    loaded = {}
    for bib_path in universe_paths:
        loaded[bib_path] = load_bib(bib_path)

    # Trim primary files down to cited-only entries (+ @string).
    for bib_path in primary_paths:
        if bib_path not in loaded:
            continue
        for entry in entry_items(loaded[bib_path]):
            if entry["type"].lower() != "string" and entry["key"] not in used_keys:
                entry["keep"] = False

    # Remove duplicate keys across the whole universe, in \bibliography order:
    # first file listed that defines a key wins, later duplicates are dropped.
    dupes_removed = []
    if not args.no_dedupe:
        seen_keys = {}
        for bib_path in universe_paths:
            for entry in entry_items(loaded[bib_path]):
                if not entry["keep"] or entry["type"].lower() == "string" or not entry["key"]:
                    continue
                key = entry["key"]
                if key in seen_keys:
                    entry["keep"] = False
                    dupes_removed.append((key, bib_path, seen_keys[key]))
                else:
                    seen_keys[key] = bib_path

    # Write out every file that changed (primary files always; secondary files
    # only if a duplicate was actually removed from them).
    all_found_keys = set()
    for bib_path in universe_paths:
        items = loaded[bib_path]
        original_text = "".join(
            item[1] if isinstance(item, tuple) else item["text"] for item in items
        )
        new_text = render_bib(items)
        changed = new_text != original_text
        is_primary = bib_path in primary_paths

        for entry in entry_items(items):
            if entry["key"]:
                all_found_keys.add(entry["key"])

        total = sum(1 for _ in entry_items(items))
        kept = sum(1 for e in entry_items(items) if e["keep"])

        if is_primary or changed:
            if not args.dry_run and changed:
                write_bib(bib_path, items, make_backup=args.backup)
            verb = "would keep" if args.dry_run else "kept"
            backup_note = "" if args.dry_run or not args.backup or not changed else \
                f"; backup saved as {bib_path.stem}.orig.bib"
            role = "" if is_primary else " (dedupe only)"
            print(f"{bib_path.name}{role}: {total} entries -> {verb} {kept} "
                  f"(removed {total - kept}){backup_note}")

    if dupes_removed:
        print(f"\nRemoved {len(dupes_removed)} duplicate key(s) (kept the copy in the "
              f"first-listed file):")
        for key, dropped_from, kept_in in dupes_removed:
            print(f"  - {key}: removed from {dropped_from.name}, kept in {kept_in.name}")

    missing = sorted(used_keys - all_found_keys)
    if missing:
        print(f"\n{len(missing)} cited key(s) not found in any bib file scanned "
              f"(check other bibliography files, or for typos):")
        for k in missing:
            print(f"  - {k}")
        sys.exit(1)

    print("\nAll cited keys were found and kept.")


if __name__ == "__main__":
    main()
