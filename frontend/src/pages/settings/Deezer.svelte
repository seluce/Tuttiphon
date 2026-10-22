<!-- Settings → Deezer stars: levels rank → stars with distribution, who gets stars, behavior in the full run. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Seg from '../../components/Seg.svelte'
  import Switch from '../../components/Switch.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import Toggle from './Toggle.svelte'
  import NumInput from './NumInput.svelte'
  import { S, changed, runTask } from '../../lib/state.svelte.js'
  import { toast, confirmDialog } from '../../lib/overlay.svelte.js'
  import { go } from '../../lib/router.svelte.js'
  import { api } from '../../lib/api.js'
  import { fmt } from '../../lib/format.js'
  import { t } from '../../lib/i18n.svelte.js'
  import { pwOk, starAccounts, getsStars, toggleStars } from '../personen/shared.js'

  const DEFAULTS = [10000, 100000, 300000, 600000, 850000]
  S.config.settings.deezer ??= {}
  const dz = S.config.settings.deezer
  dz.thresholds ??= [...DEFAULTS]

  let hist = $state.raw(null)
  let error = $state('')
  api('/api/deezer/ranks').then((r) => { hist = r }).catch((e) => { error = e.message })

  // songs per star count (0–5) by the current levels
  const per = $derived.by(() => {
    if (!hist) return null
    const th = dz.thresholds, out = [0, 0, 0, 0, 0, 0]
    hist.counts.forEach((n, k) => {
      const rank = k * hist.bucket + hist.bucket / 2
      let stars = 5
      for (let i = 0; i < 5; i++) if (rank < th[i]) { stars = i; break }
      out[stars] += n
    })
    return out
  })
  const ranked = $derived(per ? per.reduce((a, b) => a + b, 0) : 0)   // songs with a known rank
  const total = $derived(ranked || 1)
  const max = $derived(per ? Math.max(1, ...per) : 1)

  function setThreshold(i, e) {
    const el = e.currentTarget
    const next = [...dz.thresholds]
    next[i] = Math.max(0, Math.round(Number(el.value) || 0))
    if (next.some((v, k) => k && v < next[k - 1])) {
      toast(t('The levels must go up: ★ < ★★ < …'), { error: true })
      el.value = dz.thresholds[i]
      return
    }
    dz.thresholds = next
    changed()
  }

  const startTask = (steps, opts) => runTask(steps, opts).then((ok) => { if (ok) go('#/') })

  async function recalc() {
    if (!await confirmDialog(t('Recalculate stars?'), t('All stars are set again from the stored ranks with the new levels – without asking Deezer again. Stars given by hand stay, unless you allow overwriting below.'), t('Recalculate'))) return
    startTask(['deezer'], { deezer_mode: 'recalc' })
  }
  /** only for this “Check everything again”: stars given by hand are replaced too (as with “Overwrite stars given by hand”) */
  let overwrite = $state(false)
  async function full() {
    if (!await confirmDialog(t('Check everything again?'), t('All songs are looked up on Deezer again; this takes about 45–60 minutes. You can stop at any time – next time it continues from there.'), t('Start'))) return
    startTask(['deezer'], { deezer_mode: 'full', ...(overwrite ? { overwrite_manual: true } : {}) })
  }

  // every person's account – also those switched off, so they can be switched on again
  const users = $derived(starAccounts(dz))
  function toggleUser(u) {
    toggleStars(dz, u)
    changed()
  }
</script>

<Card title={t('From popularity to stars')} icon="star">
  <p class="muted small">{t('Deezer knows a popularity rank from 0 to about 1 million for almost every song – the higher, the more popular. Tuttiphon turns this into stars – and “Only the hits” takes the songs with the most stars.')}</p>
  <div class="grid grid-cols-5 gap-2.5 max-mobile:grid-cols-2">
    {#each [1, 2, 3, 4, 5] as stars, i (stars)}
      <label class="f">{t('{stars} from rank', { stars: '★'.repeat(stars) })}
        <input class="input w-full" type="number" min="0" max="1000000" step="5000" value={dz.thresholds[i]} onchange={(e) => setThreshold(i, e)} />
      </label>
    {/each}
  </div>
  <div>
    {#if error}
      <div class="err-t small">{error}</div>
    {:else if !per}
      <div class="skel h-[160px]"></div>
    {:else if !ranked}
      <p class="muted small">{t('No numbers yet – they appear with the first run.')}</p>
    {:else}
      <div class="sbars">
        {#each per as n, k (k)}
          <div class="sbar" title={t('{k} stars: {n} songs · {pct}%', { k, n: fmt(n), pct: Math.round(n / total * 100) })}>
            <span class="k">{k ? '★'.repeat(k) : t('no stars')}</span>
            <div class="tr"><i style:width="{Math.max(1.5, n / max * 100)}%"></i></div>
            <span class="n">{Math.round(n / total * 100)} %</span>
          </div>
        {/each}
      </div>
      <p class="hint mt-2">{hist.notFound
        ? t('This is how {n} songs with a known Deezer rank are distributed; {missing} were not found on Deezer.', { n: fmt(ranked), missing: fmt(hist.notFound) })
        : t('This is how {n} songs with a known Deezer rank are distributed.', { n: fmt(ranked) })}</p>
    {/if}
  </div>
  <div class="btns">
    <button class="btn sm ghost" onclick={() => { dz.thresholds = [...(hist?.defaults || DEFAULTS)]; changed() }}>{t('Defaults')}</button>
    <button class="btn sm primary" disabled={S.running} onclick={recalc}><Icon name="refresh" size={15} />{t('Recalculate stars now')}</button>
  </div>
</Card>

<Card title={t('Top tracks and refreshing')} icon="trending">
  <Row label={t('Highlight top tracks per band')} hint={t('If many songs of a band share the highest star count, the most popular get one more star. This way Symfonium sorts the top tracks correctly. Takes effect on the next run.')}>
    <Toggle label={t('Highlight top tracks per band')} obj={dz} key="topBoost" def={true} />
  </Row>
  <Row label={t('Refresh every night')} hint={t('Checks {n} songs on Deezer again every night in the time window of the night analysis – always the ones unchecked the longest, so the stars stay up to date.', { n: fmt(hist?.perNight || 1500) })}>
    <Toggle label={t('Refresh every night')} obj={dz} key="refresh" def={true} />
  </Row>
</Card>

<Card title={t('Who gets stars?')} icon="users">
  {#if users.length}
    <div class="toggles">
      {#each users as u (u)}
        <button class={['toggle', getsStars(dz, u) && 'on']} aria-pressed={getsStars(dz, u)} onclick={() => toggleUser(u)}
          title={pwOk(u) === false ? t('Password missing') : undefined}>{u}{#if pwOk(u) === false}<Icon name="lock" size={13} />{/if}</button>
      {/each}
    </div>
  {:else}
    <p class="muted small">{t('No accounts yet – create them under People first.')}</p>
  {/if}
  <div class="hint">{t('In Navidrome, stars are per account. Accounts without a password are skipped.')}</div>
  <Row label={t('Overwrite stars given by hand')} hint={t('Normally your own stars stay untouched.')}>
    <Toggle label={t('Overwrite stars given by hand')} obj={dz} key="overwriteManual" def={false} />
  </Row>
</Card>

<Card title={t('In the full run')} icon="refresh">
  <Row label={t('“Update everything” rates …')}>
    <Seg options={[['new', t('new songs only')], ['missing', t('new + not found')]]} value={dz.pipelineMode || 'new'} onchange={(v) => { dz.pipelineMode = v; changed() }} />
  </Row>
  <Row label={t('Requests per second')} hint={t('Deezer allows at most 10. Fewer = slower, but gentler.')}>
    <NumInput obj={dz} key="rate" min={1} max={10} placeholder="9" width={90} />
  </Row>
  <div class="btns">
    <button class="btn sm" disabled={S.running} onclick={() => startTask(['deezer'], { deezer_mode: 'new' })}>{t('Rate new ones now')}</button>
    <button class="btn sm" disabled={S.running} onclick={() => startTask(['deezer'], { deezer_mode: 'missing' })}>{t('Retry not found')}</button>
    <button class="btn sm" disabled={S.running} onclick={full}>{t('Check everything again')}</button>
  </div>
  {#if !dz.overwriteManual}
    <div class="grid gap-1">
      <Switch bind:checked={overwrite} label={t('also overwrite stars given by hand')} />
      <div class={['hint flex gap-1.5 items-start', overwrite && 'text-warn']}>
        <Icon name="alert" size={14} class="shrink-0 mt-0.5" />
        <span>{t('Only for “Check everything again”: stars given by hand are replaced by the Deezer rating too and are lost.')}</span>
      </div>
    </div>
  {/if}
</Card>
