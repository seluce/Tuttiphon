<!-- Live log of the running (or last) run – scrolls along. -->
<script>
  import { S } from '../../lib/state.svelte.js'

  const lineClass = (x) => (x.startsWith('━━') || x.startsWith('▶') ? 'h' : x.includes('❌') || /fehler|error/i.test(x) ? 'e'
    : x.includes('⚠') ? 'w' : x.includes('✓') || x.startsWith('■') ? 'o' : '')
  const lines = $derived(S.logLines.slice(-800).map((l) => ({ t: l.t, text: l.text, cls: lineClass(l.text) })))

  // scrolls to the end whenever lines arrive – unless you scrolled up to read (then it stays where it is)
  let atEnd = true
  const follow = (box) => {
    lines
    if (atEnd) box.scrollTop = box.scrollHeight
  }
  const scrolled = (e) => {
    const box = e.currentTarget
    atEnd = box.scrollHeight - box.scrollTop - box.clientHeight < 24
  }
</script>

<pre class="log h-[300px]" {@attach follow} onscroll={scrolled}>{#each lines as l, i (i)}<span class="t">{l.t}  </span><span class={l.cls}>{l.text + '\n'}</span>{/each}</pre>
