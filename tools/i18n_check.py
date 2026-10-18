#!/usr/bin/env python3
"""Checks the translations of the server (npm run test:i18n).

  python3 tools/i18n_check.py [files…]     only these files (default: app/*.py and tuttiphon.py)

Errors (exit code 1):
  missing   a text in _()/_s()/_n()/_sn() has no German entry in app/locales/de/*.json
  conflict  the same English text has two different German entries
  placeholder the German entry does not have exactly the {placeholders} of the English text – a value would be missing
            in German, or str.format() would fail on an unknown name. Allowed: a form the code passes along for the
            translation instead of the English one (PLACEHOLDER_ALTERNATIVES: {Every} = {every} capitalized, {owner} =
            the German possessive of {name})
  values    a call with a literal text and only keyword values that does not pass a placeholder of the English or
            German text ({n} of _n()/_sn() comes by itself) – it would raise KeyError
  german    German text left in the code (string or f-string) – data such as word lists for language detection is
            marked with "i18n-ignore" on the line, or a block between "i18n-ignore-start" and "i18n-ignore-end"
  shadow    a function assigns to _ (or _s …) and also calls it – the call raises UnboundLocalError
  bare      a visible text that does not go through the functions: log lines, exceptions, notifications and the
            "error"/"message"/"title"/"text"/"hint" values of answers
Warnings:
  dynamic   a translation function without a literal text (fine for N_() constants – mark the line "i18n-ignore")
  unused    a German entry nobody uses (only with all files)
Docstrings and comments are not checked.
"""
import ast
import json
import re
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "app" / "locales" / "de"
GERMAN = re.compile(r"[äöüÄÖÜß]|\b(und|oder|nicht|mit|für|auf|der|das|dem|den|des|ein|eine|einen|einem|ist|sind|wird|"
                    r"werden|noch|alle|alles|keine|kein|bitte|zum|zur|vom|beim|nach|über|wenn|dann|schon|auch|nur|"
                    r"hier|jetzt|heute|gestern|neu|neue|neuen|Woche|Monat|Jahr|Tage|Tagen|Fehler|gespeichert|"
                    r"gelöscht|angelegt|Sterne|Wiedergaben|Lieder|fertig|gefunden|fehlt|unbekannt|Datei|Dateien)\b")
NAMES = re.compile(r"\b(Tuttiphon|Navidrome|Symfonium|Deezer|Last\.fm|LRCLIB|NetEase|Lidarr|Opus|AAC|FLAC|WAV|AIFF|ALAC|"
                   r"APE|WavPack|MP3|ntfy|ReplayGain|MusicBrainz|Essentia|Docker|NAS|kbit/s|LUFS|dB|UID|GID|ffmpeg|"
                   r"ffprobe|mutagen|OK|ID|URL|IP|ISRC|BPM|HTTP|JSON|min|h|s|ms)\b")
FUNCS = {"_": (0,), "_s": (0,), "_n": (1, 2), "_sn": (1, 2), "N_": (0,)}
EXCEPTIONS = re.compile(r"(Error|Exception|Refused)$")
UI_KEYS = {"error", "message", "title", "text", "hint", "why", "detail", "label", "warning"}
# a translation may use another form of a value that the code passes along for it:
# rules.py: every=…, Every=every.capitalize() (German puts it first) · suggest.py: name=…, owner=possessive(name)
PLACEHOLDER_ALTERNATIVES = {"every": {"Every"}, "name": {"owner"}}


def bare(text):
    return len(re.sub(r"[^A-Za-zÄÖÜäöüß]", "", NAMES.sub("", text))) >= 3


def text_of(node):
    """Visible text of a str constant or f-string (values left out)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values if isinstance(v, ast.Constant))
    return None


def placeholders(text):
    """Names of the {placeholders} as str.format() reads them ({n:,} → n, {{ }} are no placeholders)."""
    try:
        return {re.split(r"[.\[]", name)[0] for _, name, _, _ in string.Formatter().parse(text) if name}
    except ValueError:   # a single { or } – str.format() would fail as well
        return {"{"}


def load_dict():
    merged, origin, errors = {}, {}, []
    for f in sorted(LOCALES.glob("*.json")):
        for k, v in json.loads(f.read_text(encoding="utf-8")).items():
            if k in merged and merged[k] != v:
                errors.append(f"conflict  \"{k}\": \"{merged[k]}\" ({origin[k]}) ≠ \"{v}\" ({f.name})")
            merged[k], origin[k] = v, f.name
    for k, v in merged.items():
        en, de = placeholders(k), placeholders(v)
        alt = {a for x in en for a in PLACEHOLDER_ALTERNATIVES.get(x, ())}
        missing = sorted(x for x in en - de if not PLACEHOLDER_ALTERNATIVES.get(x, set()) & de)
        extra = sorted(de - en - alt)
        if missing or extra:
            errors.append(f"placeholder {json.dumps(k, ensure_ascii=False)[:90]} ({origin[k]}):"
                          + (f" German lacks {{{'}, {'.join(missing)}}}" if missing else "")
                          + (f" German has unknown {{{'}, {'.join(extra)}}}" if extra else ""))
    return merged, origin, errors


def check(files):
    de, origin, errors = load_dict()
    warnings, used = [], set()
    # the delivered vibes, person and "all" name in app/default_config.json follow the server language
    defaults = json.loads((ROOT / "app" / "default_config.json").read_text(encoding="utf-8"))
    for text in [x["name"] for x in defaults["stile"] + defaults["personen"]] + [defaults["settings"]["allName"]]:
        used.add(text)   # names that are the same in both languages need no entry
    # name and description of every scene in app/scenes.json are English texts as well
    for sc in json.loads((ROOT / "app" / "scenes.json").read_text(encoding="utf-8")):
        for key in ("name", "description"):
            text = sc.get(key) or ""
            used.add(text)
            if text and text not in de:
                errors.append(f"missing   app/scenes.json {sc['id']}.{key} {json.dumps(text, ensure_ascii=False)}")
    for path in files:
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        ignored, block = set(), False
        for i, line in enumerate(lines, 1):
            if "i18n-ignore-start" in line:
                block = True
            if block or "i18n-ignore" in line:
                ignored.add(i)
            if "i18n-ignore-end" in line:
                block = False
        rel = path.relative_to(ROOT)
        tree = ast.parse(source)
        docstrings, keys = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                    docstrings.add(id(first.value))
        # 1. texts of the translation functions
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS:
                for i in FUNCS[node.func.id]:
                    arg = node.args[i] if i < len(node.args) else None
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        keys.add(id(arg))
                        used.add(arg.value)
                        if arg.value not in de:
                            errors.append(f"missing   {rel}:{arg.lineno} {json.dumps(arg.value, ensure_ascii=False)[:100]}")
                        # str.format() runs as soon as there are values (_n/_sn always pass n): all names must be there
                        counted = node.func.id in ("_n", "_sn")
                        if node.func.id != "N_" and (node.keywords or counted) and all(k.arg for k in node.keywords):
                            given = {k.arg for k in node.keywords} | ({"n"} if counted else set())
                            lack = sorted((placeholders(arg.value) | placeholders(de.get(arg.value, ""))) - given)
                            if lack and node.lineno not in ignored:
                                errors.append(f"values    {rel}:{arg.lineno} {json.dumps(arg.value, ensure_ascii=False)[:80]}"
                                              f" – no value for {{{'}, {'.join(lack)}}}")
                    elif node.lineno not in ignored:
                        warnings.append(f"dynamic   {rel}:{node.lineno} {node.func.id}() without a literal text")

        def flag(node, why):
            text = text_of(node)
            if text and bare(text) and node.lineno not in ignored:
                errors.append(f"bare      {rel}:{node.lineno} {json.dumps(text.strip(), ensure_ascii=False)[:100]} ({why})")
        # 1b. a scope that binds a translation function's name (e.g. "start, end, _ = …") breaks its calls – Python
        #     scopes: functions, lambdas and comprehensions have their own names
        scopes = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)

        def bound(scope):
            names = set()
            if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                names |= {a.arg for a in ast.walk(scope.args) if isinstance(a, ast.arg)}
            stack = list(ast.iter_child_nodes(scope))
            while stack:
                n = stack.pop()
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    names.add(n.id)
                if isinstance(n, scopes) or isinstance(n, ast.ClassDef):
                    continue   # its own names
                stack.extend(ast.iter_child_nodes(n))
            if isinstance(scope, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                names |= {n.id for g in scope.generators for n in ast.walk(g.target) if isinstance(n, ast.Name)}
            return names

        def calls_seeing(scope, name):
            """Calls of name() that see the binding of this scope (nested scopes that rebind it do not)."""
            found, stack = [], list(ast.iter_child_nodes(scope))
            while stack:
                n = stack.pop()
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name:
                    found.append(n)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                if isinstance(n, scopes) and name in bound(n):
                    continue
                stack.extend(ast.iter_child_nodes(n))
            return found
        for sc in ast.walk(tree):
            if isinstance(sc, scopes):
                for name in sorted(bound(sc) & set(FUNCS)):
                    hit = calls_seeing(sc, name)
                    if hit:
                        errors.append(f"shadow    {rel}:{hit[0].lineno} \"{name}\" is assigned in the same scope (line {sc.lineno}) – this {name}() call breaks")
        # 2. visible texts that bypass the functions
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
                if name in ("log", "print", "say") or EXCEPTIONS.search(name) or name in ("to_admin", "deliver", "send_to"):
                    for a in node.args[:2]:
                        flag(a, name)
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    if isinstance(k, ast.Constant) and k.value in UI_KEYS:
                        flag(v, f'"{k.value}"')
        # 3. German left in the code
        for node in ast.walk(tree):
            text = None
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings and id(node) not in keys:
                text = node.value
            if text and GERMAN.search(text) and node.lineno not in ignored:
                errors.append(f"german    {rel}:{node.lineno} {json.dumps(text.strip(), ensure_ascii=False)[:100]}")
    return de, origin, used, errors, warnings


def main():
    args = [Path(a).resolve() for a in sys.argv[1:]]
    files = args or sorted((ROOT / "app").glob("*.py")) + [ROOT / "tuttiphon.py"]
    de, origin, used, errors, warnings = check(files)
    if not args:
        warnings += [f"unused    \"{k}\" ({origin[k]})" for k in de if k not in used]
    for w in warnings:
        print("⚠ " + w)
    for e in dict.fromkeys(errors):
        print("✕ " + e)
    n = len(dict.fromkeys(errors))
    print(f"✕ {n} error(s), {len(warnings)} warning(s)" if n else f"✓ server translations complete ({len(de)} German entries, {len(warnings)} warning(s))")
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
