// Compiles single source files of the interface without building the whole app – for checking a few changed files
// while other files are still being edited.
//
//   node tools/compile-check.mjs <file.svelte|file.svelte.js|file.js> …
//
// Exit code 1 on a syntax error or a Svelte warning (the build must stay free of warnings).
// Components are compiled with the same compiler options as the build (frontend/svelte.config.js: runes).
import { readFileSync } from 'node:fs'
import { compile, compileModule, parse } from 'svelte/compiler'
import svelteConfig from '../frontend/svelte.config.js'

const options = svelteConfig.compilerOptions || {}

let failed = 0
for (const file of process.argv.slice(2)) {
  const source = readFileSync(file, 'utf8')
  try {
    let warnings = []
    if (file.endsWith('.svelte')) warnings = compile(source, { ...options, filename: file, generate: 'client' }).warnings
    else if (file.endsWith('.svelte.js')) warnings = compileModule(source, { filename: file, generate: 'client' }).warnings
    else parse(`<script module>${source}</script>`, { modern: true })
    for (const w of warnings) {
      failed++
      console.log(`⚠ ${file}:${w.start?.line ?? '?'} ${w.code}: ${w.message}`)
    }
  } catch (e) {
    failed++
    console.log(`✕ ${file}:${e.start?.line ?? '?'} ${e.message}`)
  }
}
console.log(failed ? `✕ ${failed} problem(s)` : '✓ compiles')
process.exit(failed ? 1 : 0)
