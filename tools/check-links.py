#!/usr/bin/env python3
"""Checks the links between the Markdown files (handbook, READMEs): target file exists, anchor exists.

  python3 tools/check-links.py            all *.md files of the project (without node_modules, release/, data/)

Anchors are computed like GitHub does: lowercase, punctuation removed (letters, digits, spaces, "-" and "_" stay),
spaces become "-", repeated headings get "-1", "-2" … Exit code 1 if a link points nowhere.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = ("node_modules", "release", "data", "web", "test-results", ".git")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def anchors(path):
    out, seen, fence = set(), {}, False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fence = not fence
        if fence or not line.startswith("#"):
            continue
        m = re.match(r"#+\s+(.*?)\s*#*\s*$", line)
        if not m:
            continue
        text = re.sub(r"`([^`]*)`", r"\1", m.group(1))          # code spans keep their text
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)    # links keep their text
        slug = re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-")
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        out.add(slug if n == 0 else f"{slug}-{n}")
    return out


def main():
    files = [p for p in ROOT.rglob("*.md") if not any(part in SKIP for part in p.relative_to(ROOT).parts)]
    cache, bad = {}, []
    for f in sorted(files):
        fence = False
        for no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("```"):
                fence = not fence
            if fence:
                continue
            for target in LINK.findall(line):
                if re.match(r"^(https?:|mailto:)", target):
                    continue
                file_part, _, anchor = target.partition("#")
                dest = (f.parent / file_part).resolve() if file_part else f
                if file_part and not dest.exists():
                    bad.append(f"{f.relative_to(ROOT)}:{no} missing file {target}")
                    continue
                if anchor and dest.suffix == ".md":
                    if dest not in cache:
                        cache[dest] = anchors(dest)
                    if anchor not in cache[dest]:
                        bad.append(f"{f.relative_to(ROOT)}:{no} missing anchor {target}")
    for b in bad:
        print("✕ " + b)
    print(f"✕ {len(bad)} broken link(s)" if bad else f"✓ links ok ({len(files)} files)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
