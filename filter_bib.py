#!/usr/bin/env python3
"""
filter_bib.py — strip .bib files down to only the entries actually cited
in a LaTeX document (and anything it \\input's or \\include's).

Scans your .tex file(s) for \\cite, \\citet, \\citep, \\citealt, and similar
natbib/biblatex citation commands (including comma-separated multi-key
citations and optional [..] arguments), then rewrites each given .bib file
to keep only the matching entries (plus any @string{...} declarations).

By default it also follows \\input{...} and \\include{...} directives found
in each given .tex file, recursively, so citations hiding in a separately
\\input'ed tables/figures/sections file are not missed. Use
--no-follow-inputs to scan only the file(s) you list explicitly.

Commented-out LaTeX lines (text after an unescaped %) are ignored, so a
citation left in a comment won't accidentally keep an unused entry.

Entries are located with a brace-matching scan rather than naive
line-splitting, so it correctly handles entries whose field values happen
to span multiple physical lines or contain literal '@' characters.

Usage:
    python3 filter_bib.py --tex paper.tex --bib references.bib
    python3 filter_bib.py --tex paper.tex --bib refs1.bib refs2.bib
    python3 filter_bib.py --tex paper.tex tables/extra.tex --bib references.bib
    python3 filter_bib.py --dry-run --tex paper.tex --bib references.bib
    python3 filter_bib.py --no-backup --tex paper.tex --bib references.bib
    python3 filter_bib.py --no-follow-inputs --tex paper.tex --bib references.bib

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
INPUT_RE = re.compile(r'\\(?:input|include)\{([^}]+)\}')
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
        raw_text = rf.read_text(encoding="utf-8", errors="replace")
        text = strip_comments(raw_text)
        for m in INPUT_RE.finditer(text):
            inc = m.group(1).strip()
            if not inc.lower().endswith(".tex"):
                inc += ".tex"
            queue.append(root_dir / inc)

    return ordered


def extract_used_keys(tex_files) -> set:
    keys = set()
    for tex_path in tex_files:
        raw_text = tex_path.read_text(encoding="utf-8", errors="replace")
        text = strip_comments(raw_text)
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
    parser.add_argument("--tex", type=Path, nargs="+", required=True, dest="tex_files",
                         help="LaTeX file(s) to scan for \\cite/\\citet/... commands")
    parser.add_argument("--bib", type=Path, nargs="+", required=True, dest="bib_files",
                         help="One or more .bib files to filter")
    parser.add_argument("--root-dir", type=Path, default=None,
                         help="Directory that \\input/\\include paths are resolved relative to "
                              "(default: the directory of the first --tex file)")
    parser.add_argument("--no-follow-inputs", action="store_true",
                         help="Don't follow \\input{...}/\\include{...} directives; "
                              "scan only the file(s) passed to --tex")
    parser.add_argument("--no-backup", action="store_true",
                         help="Don't save a .orig.bib backup before overwriting each .bib file")
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
