#!/usr/bin/env python3
"""
filter_bib.py — strip a .bib file down to only the entries actually cited
in a LaTeX document.

Scans a .tex file for \\cite, \\citet, \\citep, \\citealt, and similar
natbib/biblatex citation commands (including comma-separated multi-key
citations and optional [..] arguments), then rewrites each given .bib file
to keep only the matching entries (plus any @string{...} declarations).

Entries are located with a brace-matching scan rather than naive
line-splitting, so it correctly handles entries whose field values happen
to span multiple physical lines or contain literal '@' characters.

Usage:
    python3 filter_bib.py paper.tex references.bib
    python3 filter_bib.py paper.tex refs1.bib refs2.bib refs3.bib
    python3 filter_bib.py --dry-run paper.tex references.bib
    python3 filter_bib.py --no-backup paper.tex references.bib

By default, each .bib file is overwritten in place and the original is
saved next to it as "<name>.orig.bib" (only if that backup doesn't already
exist, so re-running the script never clobbers your real original).

Requires Python 3.7+. No third-party dependencies.
"""
import argparse
import re
import sys
from pathlib import Path

CITE_RE = re.compile(r'\\[A-Za-z]*[Cc]ite[A-Za-z]*\*?(?:\s*\[[^\]]*\])*\{([^}]*)\}')
ENTRY_START_RE = re.compile(r'@(\w+)\{')
KEY_RE = re.compile(r'@\w+\{\s*([^,\s}]+)\s*[,}]')


def extract_used_keys(tex_path: Path) -> set:
    text = tex_path.read_text(encoding="utf-8", errors="replace")
    keys = set()
    for match in CITE_RE.finditer(text):
        for key in match.group(1).split(","):
            key = key.strip()
            if key:
                keys.add(key)
    return keys


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


def filter_bib(bib_path: Path, used_keys: set, make_backup: bool, dry_run: bool):
    text = bib_path.read_text(encoding="utf-8", errors="replace")

    out_parts = []
    total_entries = 0
    kept_entries = 0
    found_keys = set()

    for item in parse_entries(text):
        if item[0] == "raw":
            out_parts.append(item[1])
            continue
        _, entry_type, key, entry_text = item
        total_entries += 1
        if key:
            found_keys.add(key)
        if entry_type.lower() == "string" or key in used_keys:
            out_parts.append(entry_text)
            kept_entries += 1

    if not dry_run:
        if make_backup:
            backup_path = bib_path.with_suffix(".orig.bib")
            if not backup_path.exists():
                backup_path.write_bytes(bib_path.read_bytes())
        bib_path.write_text("".join(out_parts), encoding="utf-8")

    return total_entries, kept_entries, found_keys


def main():
    parser = argparse.ArgumentParser(
        description="Strip .bib files down to only the entries cited in a LaTeX document.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("tex_file", type=Path, help="LaTeX file to scan for \\cite/\\citet/... commands")
    parser.add_argument("bib_files", type=Path, nargs="+", help="One or more .bib files to filter")
    parser.add_argument("--no-backup", action="store_true",
                         help="Don't save a .orig.bib backup before overwriting each .bib file")
    parser.add_argument("--dry-run", action="store_true",
                         help="Report what would change without writing anything")
    args = parser.parse_args()

    if not args.tex_file.exists():
        parser.error(f"tex file not found: {args.tex_file}")
    for bib_path in args.bib_files:
        if not bib_path.exists():
            parser.error(f"bib file not found: {bib_path}")

    used_keys = extract_used_keys(args.tex_file)
    print(f"Found {len(used_keys)} unique citation key(s) in {args.tex_file.name}")

    all_found_keys = set()
    for bib_path in args.bib_files:
        total, kept, found_keys = filter_bib(
            bib_path, used_keys, make_backup=not args.no_backup, dry_run=args.dry_run
        )
        all_found_keys |= found_keys
        verb = "would keep" if args.dry_run else "kept"
        suffix = "" if args.dry_run or args.no_backup else f"; backup saved as {bib_path.stem}.orig.bib"
        print(f"{bib_path.name}: {total} entries -> {verb} {kept} (removed {total - kept}){suffix}")

    missing = sorted(used_keys - all_found_keys)
    if missing:
        print(f"\n{len(missing)} cited key(s) not found in any given .bib file "
              f"(check other bibliography files, or for typos):")
        for k in missing:
            print(f"  - {k}")
        sys.exit(1)

    print("\nAll cited keys were found and kept.")


if __name__ == "__main__":
    main()
