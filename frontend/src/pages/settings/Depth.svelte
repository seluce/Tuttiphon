<!-- Analysis depth: how much of each song Tuttiphon listens to (tiles with duration and tempo matches). -->
<script>
  import Row from './Row.svelte'
  import { changed } from '../../lib/state.svelte.js'
  import { fmt } from '../../lib/format.js'
  import { t, tn } from '../../lib/i18n.svelte.js'

  /** an: settings.analysis (or a draft of it) · a: state of the sound analysis from /api/intel (audio) ·
   *  onchange: after a choice – saves by default (the setup assistant passes its own) */
  let { an, a, onchange = changed } = $props()

  /* Measured on a PC with 12 cores (6 analyses at once), about 23,000 songs; the last entry is the tempo match rate, 'reference' for the deepest level */
  const DEPTHS = $derived([
    ['schnell', t('Fast'), t('30 seconds from the middle'), t('approx. 25 min'), '79 %'],
    ['standard', t('Standard'), t('60 seconds from the middle'), t('approx. 40 min'), '88 %'],
    ['gruendlich', t('Thorough'), t('3 × 40 seconds: beginning, middle, end'), t('approx. 1.5 h'), '96 %'],
    ['tief', t('Deep'), t('the whole song; tempo section by section, then reconciled'), t('approx. 2–2.5 h'), 'reference'],
  ])
  const order = $derived(DEPTHS.map((x) => x[0]))
  const cur = $derived(an.depth || 'standard')
  // songs that were listened to with a less accurate level so far
  const behind = $derived(Object.entries(a.depths || {}).filter(([k]) => order.indexOf(k) < order.indexOf(cur)).reduce((n, [, c]) => n + c, 0))
</script>

<Row full label={t('How closely to listen?')} hint={t('The more of a song Tuttiphon hears, the more reliably it recognizes tempo and mood – especially with songs that start quiet and end loud. In return, the first pass takes longer.')}>
  <div class="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-2">
    {#each DEPTHS as [id, label, what, time, acc] (id)}
      <button type="button" class={['depth', cur === id && 'on']} onclick={() => { an.depth = id; onchange() }}>
        <b>{label}</b>
        <span class="tiny">{what}</span>
        <span class="tiny muted">{t('whole library: {time}', { time })}</span>
        <span class="tiny muted">{acc === 'reference' ? t('most accurate level') : t('Tempo matches {rate}', { rate: acc })}</span>
      </button>
    {/each}
  </div>
  <div class="hint">{t('“Tempo matches”: how often the tempo agrees with the “Deep” level. The times are rough figures; on the NAS it takes considerably longer depending on the processor. Runs in the background with a time limit per run and can be stopped at any time.')
    + (behind ? ' ' + tn(behind, '{n} song was listened to less closely so far and is measured again bit by bit, new songs first.', '{n} songs were listened to less closely so far and are measured again bit by bit, new songs first.') : '')}</div>
</Row>

<style>
  .depth { display: grid; gap: 4px; text-align: left; padding: 12px 14px; border-radius: var(--radius-card); border: 2px solid var(--line); background: var(--surface); color: inherit; font: inherit; cursor: pointer; }
  .depth:hover { border-color: var(--line-2); }
  .depth.on { border-color: var(--accent); box-shadow: 0 0 0 4px var(--accent-soft); }
</style>
