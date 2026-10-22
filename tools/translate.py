#!/usr/bin/env python3
"""Translating Tuttiphon without touching the dictionaries by hand – for corrections and new languages.

  python3 tools/translate.py export <lang> [--missing] [--dir DIR]
      writes DIR/<lang>/<area>.tsv (default DIR: translations/, not in Git) – one line per text:
      form<TAB>English<TAB>German<TAB>translation
      Edit only the last column. --missing: only the texts the language lacks.
  python3 tools/translate.py import <lang> [--dir DIR]
      reads the edited files back, checks every line and writes frontend/src/locales/<lang>/*.js and
      app/locales/<lang>/*.json. Lines are matched by their English text, so a file may hold just a few corrections;
      everything else stays as it is. An empty translation leaves the entry as it was.

Areas: ui-<file> for the interface (frontend/src/locales/de/<file>.js), srv-<file> for the server
(app/locales/de/<file>.json), srv-extra for server texts that German writes the same (they need no German entry).
form: empty for a text; for the plural of a count in a language with more forms (Polish) one line per form –
"few" (2–4, 22–24 …) and "many" (0, 5–21, 25 …).
Checks: the same {placeholders} as the English text ({Every} may stand for {every}, {owner} for {name}), the same
markup – whole tags with their attributes (<b>, <a class="link" href="…">, <Ui icon="…">, <code>) –, the plural
forms. Afterwards: npm run test:i18n.
A new language also needs its entry in frontend/src/lib/i18n.svelte.js (DICTS, LANGUAGES, LOCALES) and app/i18n.py
(LANGS, category() if its plural rules differ) – the import reminds of it.
"""
import argparse
import ast
import functools
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORMS = {"pl": ("few", "many")}   # the plural ("other") text of a count in these languages: one line per form
PH = re.compile(r"\{(\w+)(?:[:!][^{}]*)?\}")   # also {start:%d/%m}
TAG = re.compile(r"</?[A-Za-z][^>]*>")          # whole tags with their attributes
ALT = {"Every": "every", "owner": "name"}   # forms of a value the code passes along for the translation
LANG = re.compile(r"[a-z]{2}")


def ui_dict(path):
    """The dictionary of a JS locale file (export default {...}) – read by node, which the build needs anyway."""
    script = (f"const d=(await import({json.dumps(path.resolve().as_uri())})).default;"
              "process.stdout.write(JSON.stringify(Object.entries(d)))")
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return dict(json.loads(out.stdout))


def plural_keys(root=ROOT):
    """English plural texts of counts: tn()/plural()/tword() in the interface, _n()/_sn() on the server."""
    return _plural_keys(str(root))


@functools.lru_cache(maxsize=4)
def _plural_keys(root):
    root = Path(root)
    keys = set()
    for f in [*(root / "frontend/src").rglob("*.svelte"), *(root / "frontend/src").rglob("*.js")]:
        if "/locales/" in f.as_posix():
            continue
        s = f.read_text(encoding="utf-8")
        for m in re.finditer(r"\b(tn|plural|tword)\(", s):   # the third argument, by counting brackets
            i, depth, args, cur, quote = m.end(), 1, [], "", None
            while i < len(s) and depth:
                c = s[i]
                if quote:   # inside a string: commas and brackets are text ("{n} songs, new every week")
                    cur += c
                    if c == "\\":
                        cur += s[i + 1:i + 2]
                        i += 1
                    elif c == quote:
                        quote = None
                    i += 1
                    continue
                if c in "'\"`":
                    quote = c
                depth += c in "([{"
                depth -= c in ")]}"
                if c == "," and depth == 1:
                    args.append(cur)
                    cur = ""
                elif depth:
                    cur += c
                i += 1
            args.append(cur)
            lit = re.fullmatch(r"\s*'((?:[^'\\]|\\.)*)'\s*", args[2]) if len(args) > 2 else None
            if lit:
                keys.add(lit.group(1).replace("\\'", "'"))
    for f in [*(root / "app").glob("*.py"), root / "tuttiphon.py"]:
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("_n", "_sn") \
                    and len(node.args) > 2 and isinstance(node.args[2], ast.Constant):
                keys.add(node.args[2].value)
    return keys


def server_extra(root=ROOT):
    """Server texts without a German entry (the same in German) – they need a translation all the same."""
    sys.path.insert(0, str(root / "tools"))
    import i18n_check
    files = [p.resolve() for p in sorted((root / "app").glob("*.py"))] + [(root / "tuttiphon.py").resolve()]
    de, _origin, used, _errors, _warnings = i18n_check.check(files)
    return sorted(k for k in used if k and k not in de)


def areas(root=ROOT):
    """[(area, German dictionary)] in a fixed order – read once per run."""
    return _areas(str(root))


@functools.lru_cache(maxsize=4)
def _areas(root):
    root = Path(root)
    out = []
    for p in sorted((root / "frontend/src/locales/de").glob("*.js")):
        if p.name != "index.js":
            out.append((f"ui-{p.stem}", ui_dict(p)))
    for p in sorted((root / "app/locales/de").glob("*.json")):
        out.append((f"srv-{p.stem}", json.loads(p.read_text(encoding="utf-8"))))
    out.append(("srv-extra", {k: k for k in server_extra(root)}))
    return out


def target(area, lang, root=ROOT):
    if area.startswith("ui-"):
        return root / "frontend/src/locales" / lang / f"{area[3:]}.js"
    return root / "app/locales" / lang / f"{area[4:]}.json"


def current(area, lang, root=ROOT):
    path = target(area, lang, root)
    if not path.exists():
        return {}
    return ui_dict(path) if area.startswith("ui-") else json.loads(path.read_text(encoding="utf-8"))


def cell(text):
    return str(text).replace("\t", " ").replace("\n", "\\n")


def uncell(text):
    return text.replace("\\n", "\n")


def export(lang, out_dir, missing=False, root=ROOT):
    plurals = plural_keys(root)
    folder = Path(out_dir) / lang
    folder.mkdir(parents=True, exist_ok=True)
    total = 0
    for area, de in areas(root):
        have = current(area, lang, root)
        rows = []
        for en, ger in de.items():
            now = have.get(en)
            if missing and now:
                continue
            if en in plurals and lang in FORMS:
                for form in FORMS[lang]:
                    rows.append((form, en, ger, now.get(form, "") if isinstance(now, dict) else ""))
            else:
                rows.append(("", en, ger, (now.get("other") or next(iter(now.values()), "")) if isinstance(now, dict) else now or ""))
        path = folder / f"{area}.tsv"
        if rows:
            path.write_text("".join("\t".join(cell(x) for x in r) + "\n" for r in rows), encoding="utf-8")
            total += len(rows)
        elif path.exists():
            path.unlink()
    print(f"{lang}: {total} line(s) in {folder}")
    return total


def check_text(en, text):
    """Problems of one translation against its English text."""
    out = []
    if {ALT.get(x, x) for x in PH.findall(en)} != {ALT.get(x, x) for x in PH.findall(text)}:
        out.append(f"placeholders {sorted(set(PH.findall(text)))} instead of {sorted(set(PH.findall(en)))}")
    tags = lambda s: sorted(re.sub(r"\s+", " ", t) for t in TAG.findall(s))   # noqa: E731
    if tags(en) != tags(text):   # an href, onclick … of its own would run in the browser ({@html})
        out.append("markup differs from the English text (tags and their attributes)")
    return out


def js_str(s):
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"


def write(area, lang, entries, order, root=ROOT):
    """Write a locale file: the entries in the order of the German file."""
    path = target(area, lang, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = {k: entries[k] for k in order if k in entries}
    if area.startswith("ui-"):
        lines = [f"// Same keys as ../de/{area[3:]}.js", "export default {"]
        for k, v in ordered.items():
            if isinstance(v, dict):
                lines.append(f"  {js_str(k)}: {{ " + ", ".join(f"{f}: {js_str(x)}" for f, x in v.items()) + " },")
            else:
                lines.append(f"  {js_str(k)}:\n    {js_str(v)},")
        path.write_text("\n".join(lines + ["}"]) + "\n", encoding="utf-8")
    else:
        path.write_text(json.dumps(ordered, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    index = root / "frontend/src/locales" / lang / "index.js"
    if area.startswith("ui-") and not index.exists():
        de = (root / "frontend/src/locales/de/index.js").read_text(encoding="utf-8")
        index.write_text(de.replace("German translations", "Translations").replace("'German text'", "'translation'"),
                         encoding="utf-8")


def import_(lang, in_dir, root=ROOT):
    folder = Path(in_dir) / lang
    if not folder.is_dir():
        print(f"✕ no folder {folder} – export first")
        return 1
    plurals = plural_keys(root)
    known = dict(areas(root))
    problems, changed = [], 0
    for path in sorted(folder.glob("*.tsv")):
        area = path.stem
        if area not in known:
            problems.append(f"{path.name}: unknown area")
            continue
        order = list(known[area])
        entries = current(area, lang, root)
        got, before = {}, changed
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) != 4:
                problems.append(f"{path.name}:{n}: needs 4 columns (form, English, German, translation)")
                continue
            form, en, _ger, text = parts[0].strip(), uncell(parts[1]), parts[2], uncell(parts[3])
            if en not in known[area]:
                problems.append(f"{path.name}:{n}: the English text is not (or no longer) in the app: {en[:60]!r}")
                continue
            if not text.strip():
                continue
            bad = check_text(en, text)
            if bad:
                problems += [f"{path.name}:{n}: {b} – {en[:60]!r}" for b in bad]
                continue
            got.setdefault(en, {})[form] = text
        for en, forms in got.items():
            if en in plurals and lang in FORMS:
                old = entries.get(en) if isinstance(entries.get(en), dict) else {}
                new = {**old, **{f: v for f, v in forms.items() if f}}
                lacking = [f for f in FORMS[lang] if f not in new]
                if lacking:
                    problems.append(f"{area}: plural forms {lacking} missing – {en[:60]!r}")
                    continue
                value = {f: new[f] for f in FORMS[lang]}
            elif "" in forms:
                value = forms[""]
            else:
                problems.append(f"{area}: a form given for a text that has none – {en[:60]!r}")
                continue
            if entries.get(en) != value:
                entries[en] = value
                changed += 1
        if changed > before:
            write(area, lang, entries, order, root)
    for p in problems:
        print("✕", p)
    print(f"{lang}: {changed} entr{'y' if changed == 1 else 'ies'} changed, {len(problems)} problem(s) – then: npm run test:i18n")
    if f'"{lang}"' not in (root / "app/i18n.py").read_text(encoding="utf-8") \
            or f"{lang}: () => import" not in (root / "frontend/src/lib/i18n.svelte.js").read_text(encoding="utf-8"):
        print(f"  A new language: add “{lang}” to DICTS, LANGUAGES and LOCALES in frontend/src/lib/i18n.svelte.js and to LANGS"
              " (and category(), if its plural rules differ) in app/i18n.py.")
    return 1 if problems else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export and import the translations of Tuttiphon.")
    ap.add_argument("action", choices=("export", "import"))
    ap.add_argument("lang", help="language key, e.g. fr")
    ap.add_argument("--dir", default=str(ROOT / "translations"), help="folder of the TSV files (default: translations/)")
    ap.add_argument("--missing", action="store_true", help="export: only the texts the language lacks")
    args = ap.parse_args(argv)
    if not LANG.fullmatch(args.lang) or args.lang in ("en", "de"):
        ap.error("a two-letter language other than en (the source) and de (the reference)")
    if args.action == "export":
        export(args.lang, args.dir, args.missing)
        return 0
    return import_(args.lang, args.dir)


if __name__ == "__main__":
    sys.exit(main())
