// Checks the translations of the interface (npm run test:i18n).
//
//   node tools/i18n-check.mjs [files…]      only these source files (default: all of frontend/src)
//
// Errors (exit code 1):
//   missing     a text in t()/tn()/plural() has no German entry in frontend/src/locales/de/
//   conflict    the same English text has two different German entries
//   placeholder the German entry does not have exactly the {name} placeholders of the English text – a value would be
//               missing in German, or the German would show “{name}” literally
//   values      t()/tn() with a literal params object that lacks a placeholder of the English or German text ({n} of
//               tn() comes by itself)
//   german      German text left in the code (string literal or markup) instead of English + t()
//   shadow      a variable named t hides the translation function
//   bare        visible text without t(): text in markup, in attributes such as label/hint/title/placeholder, and the
//               texts of toast(), confirmDialog() and new Error() – it would stay English in every language
//   static      t() runs only once – at module level or while a component is set up, outside a function – so the
//               text would not follow a change of language. That includes functions that run right away there:
//               (() => t('…'))() and the callbacks of list.map/filter/reduce/find/some/every/flatMap/sort/forEach …,
//               Array.from(x, fn) and Object.fromEntries(…). Fix: $derived(…) in a component, translated(() => …)
//               at module level, or a function called later. Allowed: $state(t('…')) / $state.raw(t('…')) with a
//               single t()/tn()/plural() as the direct argument (a deliberate starting value someone edits).
// Warnings:
//   dynamic     t() with a non-literal argument – the checker cannot see that text (only for data from the server)
//   unused      a German entry nobody uses (only with all files)
// Comments are ignored. A line containing "i18n-ignore" is skipped by the german, bare, shadow and dynamic checks;
// the static check skips only a line marked "i18n-ignore static" (a text that may deliberately stay as it is).
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { parse } from 'svelte/compiler'

const ROOT = new URL('..', import.meta.url).pathname
const SRC = join(ROOT, 'frontend/src')
const LOCALES = join(SRC, 'locales')

const walkDir = (dir) => readdirSync(dir).flatMap((n) => {
  const p = join(dir, n)
  if (statSync(p).isDirectory()) return p === LOCALES ? [] : walkDir(p)
  return /\.(svelte|js)$/.test(n) ? [p] : []
})

const args = process.argv.slice(2)
const files = args.length ? args.map((f) => join(process.cwd(), f)) : walkDir(SRC)

// German dictionary: every file in locales/de except index.js
const dict = {}, origin = {}, errors = [], warnings = []
for (const n of readdirSync(join(LOCALES, 'de')).filter((n) => n.endsWith('.js') && n !== 'index.js').sort()) {
  const part = (await import(join(LOCALES, 'de', n))).default
  for (const [k, v] of Object.entries(part)) {
    if (k in dict && dict[k] !== v) errors.push(`conflict  "${k}": "${dict[k]}" (${origin[k]}) ≠ "${v}" (${n})`)
    dict[k] = v
    origin[k] = n
  }
}

// {name} placeholders as t() fills them (lib/i18n.svelte.js) – the German must use the same ones
const placeholders = (s) => new Set([...String(s).matchAll(/\{(\w+)\}/g)].map((m) => m[1]))
for (const [k, v] of Object.entries(dict)) {
  const en = placeholders(k), de = placeholders(v)
  const missing = [...en].filter((x) => !de.has(x)), extra = [...de].filter((x) => !en.has(x))
  if (missing.length || extra.length) {
    errors.push(`placeholder "${k.slice(0, 80)}" (${origin[k]}):${missing.length ? ` German lacks {${missing.join('}, {')}}` : ''}`
      + `${extra.length ? ` German has unknown {${extra.join('}, {')}}` : ''}`)
  }
}

const GERMAN = /[äöüÄÖÜß]|\b(und|oder|nicht|mit|für|auf|der|das|dem|den|des|ein|eine|einen|einem|ist|sind|wird|werden|noch|alle|alles|keine|kein|bitte|zum|zur|vom|beim|nach|über|wenn|dann|schon|auch|nur|hier|jetzt|heute|gestern|morgen|neu|neue|neuen|Woche|Monat|Jahr|Tage|Tagen|Fehler|Speichern|Abbrechen|Löschen|Einstellungen|gespeichert|gelöscht|angelegt|Sterne|Wiedergaben|Vorschläge|hören|gehört|Lieder)\b/
// Names and units that look the same in every language
const NAMES = /\b(Tuttiphon|Navidrome|Symfonium|Deezer|Last\.fm|LRCLIB|NetEase|Lidarr|Opus|AAC|FLAC|WAV|AIFF|ALAC|APE|WavPack|MP3|ntfy|ReplayGain|MusicBrainz|Essentia|Docker|UGOS|UGREEN|NAS|GitHub|iPhone|iPad|Android|Mac|Chrome|Safari|Firefox|kbit\/s|LUFS|dB|UID|GID|ffmpeg|ffprobe|mutagen|OK|ID|URL|IP|ISRC|BPM|KI|AI|Hz|kHz|MB|GB|KB|min|h|s|ms|px)\b/g
const bare = (text) => text.replace(NAMES, '').replace(/[^\p{L}]/gu, '').length >= 3
const UI_ATTRS = new Set(['label', 'hint', 'title', 'placeholder', 'aria-label', 'alt', 'text', 'sub', 'desc', 'description', 'eyebrow', 'empty', 'confirm', 'cancel', 'action'])
const UI_CALLS = new Set(['toast', 'confirmDialog', 'promptDialog', 'alert'])
const used = new Set()

function walk(node, visit, parent = null) {
  if (!node || typeof node !== 'object') return
  if (Array.isArray(node)) { for (const x of node) walk(x, visit, parent); return }
  if (typeof node.type === 'string') visit(node, parent)
  for (const [k, v] of Object.entries(node)) {
    if (k === 'parent' || k === 'metadata' || k === 'leadingComments' || k === 'trailingComments') continue
    if (v && typeof v === 'object') walk(v, visit, typeof node.type === 'string' ? node : parent)
  }
}

const literal = (n) => (n?.type === 'Literal' && typeof n.value === 'string' ? n.value
  : n?.type === 'TemplateLiteral' && n.expressions.length === 0 ? n.quasis[0].value.cooked : null)

for (const file of files) {
  const rel = relative(ROOT, file)
  const source = readFileSync(file, 'utf8')
  const lines = source.split('\n')
  let ast
  try {
    ast = parse(file.endsWith('.svelte') ? source : `<script module>${source}</script>`, { modern: true })
  } catch (e) {
    errors.push(`${rel}: cannot parse (${e.message})`)
    continue
  }
  const shift = file.endsWith('.svelte') ? 0 : '<script module>'.length
  const lineOf = (pos) => source.slice(0, Math.max(0, pos - shift)).split('\n').length
  const skip = (pos) => lines[lineOf(pos) - 1]?.includes('i18n-ignore')
  const keys = new Set()   // literal arguments of t()/tn()/plural() – not "German left in the code" themselves

  walk(ast, (n) => {
    if (n.type !== 'CallExpression' || n.callee?.type !== 'Identifier') return
    const name = n.callee.name
    const texts = name === 't' ? [n.arguments[0]] : name === 'tn' || name === 'plural' ? [n.arguments[1], n.arguments[2]] : null
    if (!texts) return
    // values handed over as an object literal: they must cover the placeholders (without one, the text is filled
    // elsewhere – e.g. {name} as an interface button in the help)
    const params = name === 't' ? n.arguments[1] : name === 'tn' ? n.arguments[3] : null
    const given = params?.type === 'ObjectExpression' && params.properties.every((p) => p.type === 'Property' && !p.computed)
      ? new Set([...params.properties.map((p) => p.key.name ?? p.key.value), ...(name === 'tn' ? ['n'] : [])])
      : name === 'tn' && !params ? new Set(['n']) : null
    for (const a of texts) {
      const s = literal(a)
      if (s == null) {
        if (a && !skip(n.start)) warnings.push(`dynamic   ${rel}:${lineOf(n.start)} ${name}() without a literal text`)
        continue
      }
      keys.add(a)
      used.add(s)
      if (!(s in dict)) errors.push(`missing   ${rel}:${lineOf(a.start)} "${s}"`)
      if (given) {
        const lack = [...new Set([...placeholders(s), ...placeholders(dict[s] ?? '')])].filter((x) => !given.has(x))
        if (lack.length) errors.push(`values    ${rel}:${lineOf(a.start)} "${s.slice(0, 70)}" – no value for {${lack.join('}, {')}}`)
      }
    }
  })

  // a variable called t hides the translation function in its scope (x.map((t) => t.name) …)
  if (/import\s*\{[^}]*\bt\b[^}]*\}\s*from\s*['"][^'"]*i18n/.test(source)) {
    const binds = (pat) => pat?.type === 'Identifier' ? pat.name === 't'
      : pat?.type === 'ArrayPattern' ? pat.elements.some(binds)
      : pat?.type === 'ObjectPattern' ? pat.properties.some((pr) => binds(pr.value ?? pr.argument))
      : pat?.type === 'AssignmentPattern' ? binds(pat.left) : pat?.type === 'RestElement' ? binds(pat.argument) : false
    walk(ast, (n) => {
      const hit = (n.type === 'VariableDeclarator' && binds(n.id))
        || (/Function/.test(n.type) && n.params?.some(binds))
        || (n.type === 'EachBlock' && (binds(n.context) || n.index === 't'))
        || (n.type === 'CatchClause' && binds(n.param))
        || (n.type === 'SnippetBlock' && n.parameters?.some(binds))
      if (hit && !skip(n.start)) errors.push(`shadow    ${rel}:${lineOf(n.start)} a variable "t" hides the translation function here`)
    })
  }

  // visible text that does not go through t()
  const flagBare = (node, text) => {
    if (text && bare(text) && !skip(node.start)) errors.push(`bare      ${rel}:${lineOf(node.start)} ${JSON.stringify(text.trim().slice(0, 90))}`)
  }
  walk(ast, (n, parent) => {
    if (n.type === 'Text' && parent?.type !== 'StyleSheet' && parent?.type !== 'Attribute' && parent?.type !== 'StyleDirective') flagBare(n, n.data)
    // <form action="/api/…"> is an address, not text
    if (n.type === 'RegularElement' && n.name === 'form') for (const a of n.attributes) if (a.name === 'action') a.name = '(form-action)'
    if (n.type === 'Attribute' && UI_ATTRS.has(n.name) && Array.isArray(n.value)) {
      for (const v of n.value) if (v.type === 'Text') flagBare(v, v.data)
    }
    if (n.type === 'Attribute' && UI_ATTRS.has(n.name) && n.value?.type === 'ExpressionTag') {
      const s = literal(n.value.expression)
      if (s != null) flagBare(n.value.expression, s)
    }
    // options={[['wert', 'Beschriftung'], …]} (Seg, Select) – the second entry is visible
    if (n.type === 'Attribute' && n.name === 'options' && n.value?.expression?.type === 'ArrayExpression') {
      for (const el of n.value.expression.elements) {
        if (el?.type === 'ArrayExpression' && el.elements.length >= 2) {
          const s = literal(el.elements[1]); if (s != null) flagBare(el.elements[1], s)
        }
      }
    }
    // { label: '…', title: '…', text: '…', hint: '…' } – data for menus, steps, guides
    if (n.type === 'Property' && !n.computed && UI_ATTRS.has(n.key?.name ?? n.key?.value)) {
      const s = literal(n.value); if (s != null) flagBare(n.value, s)
    }
    if (n.type === 'CallExpression' && n.callee?.type === 'Identifier' && UI_CALLS.has(n.callee.name)) {
      for (const a of n.arguments) { const s = literal(a); if (s != null) flagBare(a, s) }
    }
    if (n.type === 'NewExpression' && n.callee?.name === 'Error') {
      const s = literal(n.arguments[0]); if (s != null) flagBare(n.arguments[0], s)
    }
  })

  // texts translated only once (see "static" above)
  const skipStatic = (pos) => /i18n-ignore static\b/.test(lines[lineOf(pos) - 1] || '')
  const isFn = (n) => n?.type === 'ArrowFunctionExpression' || n?.type === 'FunctionExpression'
  const isText = (n) => n?.type === 'CallExpression' && n.callee?.type === 'Identifier' && ['t', 'tn', 'plural'].includes(n.callee.name)
  // '$state', '$state.raw', 'Array.from' … – the name of a called function or method on a plain name
  const calleeName = (c) => (c.callee?.type === 'Identifier' ? c.callee.name
    : c.callee?.type === 'MemberExpression' && !c.callee.computed && c.callee.object?.type === 'Identifier'
      ? `${c.callee.object.name}.${c.callee.property?.name}` : null)
  // synchronous helpers: a function handed to them runs right away – just as often as the code around it
  const RUN_NOW = new Set(['map', 'filter', 'reduce', 'reduceRight', 'find', 'findIndex', 'findLast', 'findLastIndex', 'some',
    'every', 'flatMap', 'sort', 'toSorted', 'forEach'])
  const runsNow = (c) => ['Array.from', 'Object.fromEntries'].includes(calleeName(c))
    || (c.callee?.type === 'MemberExpression' && !c.callee.computed && RUN_NOW.has(c.callee.property?.name))
  const fnBody = (fn) => { once(fn.params); once(fn.body) }
  const once = (n) => {
    if (!n || typeof n !== 'object') return
    if (Array.isArray(n)) { for (const x of n) once(x); return }
    if (typeof n.type !== 'string' || /Function/.test(n.type)) return   // a function runs later – unless called right away
    if (n.type === 'CallExpression') {
      const name = calleeName(n)
      if (['$derived', '$derived.by', 'translated'].includes(name)) return   // built again for each language
      // $state(t('…')): a deliberate starting value someone edits – only a single t() as the direct argument
      if (['$state', '$state.raw'].includes(name) && isText(n.arguments[0])) { once(n.arguments[0].arguments); return }
      if (isText(n)) {
        if (!skipStatic(n.start)) errors.push(`static    ${rel}:${lineOf(n.start)} ${source.slice(n.start - shift, n.start - shift + 60).split('\n')[0]} – translated only once`)
        return
      }
      if (isFn(n.callee)) { fnBody(n.callee); once(n.arguments); return }   // (() => …)()
      if (runsNow(n)) {   // list.map((x) => …), Array.from(x, (y) => …)
        once(n.callee)
        for (const a of n.arguments) if (isFn(a)) fnBody(a); else once(a)
        return
      }
    }
    for (const [k, v] of Object.entries(n)) {
      if (k !== 'parent' && k !== 'metadata' && v && typeof v === 'object') once(v)
    }
  }
  if (ast.module) once(ast.module.content)
  if (ast.instance) once(ast.instance.content)

  walk(ast, (n, parent) => {
    let text = null
    if (n.type === 'Text' && parent?.type !== 'StyleSheet') text = n.data
    else if ((n.type === 'Literal' && typeof n.value === 'string') || n.type === 'TemplateElement') {
      if (keys.has(n) || [...keys].some((k) => k.type === 'TemplateLiteral' && k.quasis.includes(n))) return
      if (parent?.type === 'ImportDeclaration' || parent?.type === 'ExportAllDeclaration' || parent?.type === 'ExportNamedDeclaration') return
      text = n.type === 'Literal' ? n.value : n.value.cooked
    }
    if (text && GERMAN.test(text) && !skip(n.start)) {
      errors.push(`german    ${rel}:${lineOf(n.start)} ${JSON.stringify(text.trim().slice(0, 90))}`)
    }
  })
}

if (!args.length) {
  for (const k of Object.keys(dict)) if (!used.has(k)) warnings.push(`unused    "${k}" (${origin[k]})`)
}
for (const w of warnings) console.log('⚠ ' + w)
for (const e of errors) console.log('✕ ' + e)
console.log(errors.length ? `✕ ${errors.length} error(s), ${warnings.length} warning(s)` : `✓ translations complete (${Object.keys(dict).length} German entries, ${warnings.length} warning(s))`)
process.exit(errors.length ? 1 : 0)
