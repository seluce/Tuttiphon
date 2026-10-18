<!-- Settings → Intelligence: sound analysis (with analysis depth and night analysis), AI sound analysis (with key,
     tempo, instruments and sound vectors), audio fingerprints (same recording twice), Last.fm, classifying new bands,
     manual runs. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Seg from '../../components/Seg.svelte'
  import Select from '../../components/Select.svelte'
  import Field from '../../components/Field.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import Toggle from './Toggle.svelte'
  import NumInput from './NumInput.svelte'
  import Depth from './Depth.svelte'
  import { S, changed, snapshot, save, loadStatus, runTask } from '../../lib/state.svelte.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { go } from '../../lib/router.svelte.js'
  import { api } from '../../lib/api.js'
  import { fmt, serverDate } from '../../lib/format.js'
  import { t, tn } from '../../lib/i18n.svelte.js'

  S.config.settings.analysis ??= {}
  const an = S.config.settings.analysis
  S.config.settings.welten ??= { auto: true }
  const wl = S.config.settings.welten
  an.night ??= {}
  const env = $derived(S.status?.env || {})
  const locked = $derived((env.locked || []).includes('LASTFM_API_KEY'))

  let d = $state.raw(null)
  let error = $state('')
  const load = () => api('/api/intel').then((r) => { d = r; error = '' }).catch((e) => { error = e.message })
  // load only once a running save is done (after “Undo” the section is rebuilt)
  save().then(load)

  const a = $derived(d?.audio || {})
  const m = $derived(d?.ml || {})
  const l = $derived(d?.lastfm || {})
  const pct = $derived(a.total ? Math.round(a.analysed / a.total * 100) : 0)
  const mlPct = $derived(a.total ? Math.round(m.analysed / a.total * 100) : 0)
  const curPct = $derived(a.total ? Math.round((m.current || 0) / a.total * 100) : 0)   // with the current AI version

  /* audio fingerprints (same recording twice) */
  const fp = $derived(d?.fingerprints || {})
  const fpPct = $derived(fp.total ? Math.round((fp.songs || 0) / fp.total * 100) : 0)
  const fpInfo = $derived([
    fp.open ? tn(fp.open, '{n} song still open', '{n} songs still open') : null,
    fp.errors ? t('{n} not readable', { n: fmt(fp.errors) }) : null,
    fp.lastRun ? t('last run {when}', { when: serverDate(fp.lastRun) }) : null,
  ].filter(Boolean).join(' · '))

  const NIGHT = { from: '01:00', to: '05:00' }   // shown when nothing is set
  function setNight(key, e) {
    const el = e.currentTarget
    if (!/^\d{2}:\d{2}$/.test(el.value)) return
    const other = key === 'from' ? 'to' : 'from'
    if (el.value === (an.night[other] || NIGHT[other])) {   // an empty time window: the night analysis would never run
      toast(t('Start and end must not be the same.'), { error: true })
      el.value = an.night[key] || NIGHT[key]
      return
    }
    an.night[key] = el.value
    changed()
  }
  const moodMax = $derived(Math.max(1, ...Object.values(a.moods || {})))

  /* Last.fm key */
  let key = $state('')
  let out = $state({ text: '', cls: '' })
  async function test() {
    out = { text: t('testing …'), cls: 'muted' }
    const r = await api('/api/lastfm/test', { body: { key: key.trim() } }).catch((e) => ({ ok: false, error: e.message }))
    out = { text: r.ok ? t('✓ Last.fm responds, e.g. Nightwish: {tags}', { tags: r.tags.slice(0, 3).join(', ') }) : `✕ ${r.error}`, cls: r.ok ? 'ok-t' : 'err-t' }
    return r.ok
  }
  async function saveKey() {
    if (!key.trim()) { toast(t('Please enter the key'), { error: true }); return }
    if (!await test()) return
    try {
      await api('/api/env', { method: 'PUT', body: { LASTFM_API_KEY: key.trim() } })
    } catch (e) {
      toast(e.message, { error: true })
      return
    }
    key = ''
    toast(t('Last.fm key saved ✓'))
    loadStatus()
  }

  /* Accept suggestions – then fetch the list fresh */
  async function addTo(x) {
    const w = S.config.welten.find((y) => y.id === x.welt)
    if (!w) return
    snapshot()
    w.artists ??= []
    w.artists.push(x.artist)
    changed()
    toast(`${x.artist} → ${w.name}`, { undo: true })
    await save()
    load()
  }
  async function addStil(x) {
    const st = S.config.stile.find((y) => y.id === x.stil)
    if (!st) return
    snapshot()
    st.artists ??= []
    st.artists.push(x.artist)
    changed()
    toast(`${x.artist} → ${st.name}`, { undo: true })
    await save()
    load()
  }

  const startTask = (steps, opts) => runTask(steps, opts).then((ok) => { if (ok) go('#/') })
</script>

{#if error}
  <div class="err-t">{error}</div>
{:else if !d}
  <div class="skel h-[120px]"></div>
{:else}
  <Card title={t('Sound analysis')} icon="waves">
    <p class="muted small">{t('Tuttiphon listens to every song – completely locally, with no cloud and no costs. This gives sound vibes such as “Falling asleep” or “Running wild”, mixes that wind down calmly and the classification of new bands. A pass has two stages:')}</p>
    <div class="grid gap-2.5">
      <div class="stage">
        <span class="num">1</span>
        <div class="min-w-0">
          <b>{t('Measure')}</b> <span class="muted small">{t('– tempo, energy, danceability, timbre')}</span>
          <div class="progress my-1.5"><i style:width="{pct}%"></i></div>
          <div class="small">{t('{done} of {total} songs · {pct}%', { done: fmt(a.analysed || 0), total: fmt(a.total || 0), pct })}</div>
        </div>
      </div>
      <div class="stage">
        <span class="num">2</span>
        <div class="min-w-0">
          <b>{t('AI')}</b> <span class="muted small">{t('– mood, vocals or instrumental, acoustic, music style')}</span>
          {#if !m.available}
            <div class="small warn-t mt-1">{m.reason || t('Not available.')}</div>
          {:else}
            <div class="progress my-1.5"><i style:width="{mlPct}%"></i></div>
            <div class="small">{t('{done} of {total} songs · {pct}%', { done: fmt(m.analysed || 0), total: fmt(a.total || 0), pct: mlPct })}
              {#if m.styles?.length}<span class="muted">{t(' · most common: {styles}', { styles: m.styles.slice(0, 4).map((x) => x[0]).join(', ') })}</span>{/if}</div>
            <div class="grid gap-0.5 mt-1.5 small">
              <div>{t('With the current AI version (key, tempo, instruments, how easy to listen to): {done} of {total} songs · {pct}%', { done: fmt(m.current || 0), total: fmt(a.total || 0), pct: curPct })}</div>
              <div>{t('Sound vectors for similar bands and smooth transitions: {n} songs', { n: fmt(m.vectors || 0) })}</div>
              {#if m.instruments?.length}<div class="muted">{t('Most common instruments: {list}', { list: m.instruments.slice(0, 5).map((x) => x[0]).join(', ') })}</div>{/if}
              {#if m.themes?.length}<div class="muted">{t('Most common themes: {list}', { list: m.themes.slice(0, 5).map((x) => x[0]).join(', ') })}</div>{/if}
            </div>
            {#if m.analysed && (m.current || 0) < m.analysed}
              <div class="hint mt-1">{t('After an update the AI listens to the library once more – new songs first, the rest over the next nights. Until then the earlier results keep working.')}</div>
            {/if}
          {/if}
        </div>
      </div>
    </div>
    <div class="hint">{t('The AI takes each song right after its measurement, and only songs already measured. In the first pass this means it really gets going once the measurement is almost done. The night analysis does both at night – the first pass takes several nights on the NAS, after that only new songs are left.')}{a.lastRun ? t(' Last measurement: {when}.', { when: serverDate(a.lastRun) }) : ''}{m.lastRun ? t(' AI last run: {when}.', { when: serverDate(m.lastRun) }) : ''}</div>
    <Depth {an} {a} />
    {#if a.analysed}
      <div class="sbars">
        {#each Object.entries(d.moods || {}) as [k, label] (k)}
          <div class="sbar" title={t('{label}: {n} songs', { label, n: fmt(a.moods?.[k] || 0) })}>
            <span class="k">{label}</span>
            <div class="tr"><i style:width="{Math.max(1.5, (a.moods?.[k] || 0) / moodMax * 100)}%"></i></div>
            <span class="n">{fmt(a.moods?.[k] || 0)}</span>
          </div>
        {/each}
      </div>
    {/if}
    {#if a.bpm}
      <div class="hint">{t('Tempo: mostly between {low} and {high} BPM, median {median}.', { low: a.bpm.p10, high: a.bpm.p90, median: a.bpm.median })}</div>
    {/if}
    <Row label={t('Turn on sound analysis')}><Toggle obj={an} key="enabled" /></Row>
    <Row label={t('Add AI')} hint={t('Stage 2. Without AI, only the measurement runs.')}><Toggle obj={an} key="ml" /></Row>
    <Row label={t('Night analysis')} hint={t('At night Tuttiphon works through everything still open with no time limit – first the measurement, then the AI. Ends at the latest at the end of the time window and before the daily refresh. New music arriving during this time is processed afterwards. The nightly Deezer refresh and the weekly cover search also run in this window.')}>
      <Toggle obj={an.night} key="enabled" />
    </Row>
    {#if an.night.enabled ?? true}
      <Row label={t('Time window')}>
        <span class="flex items-center gap-2">
          <input class="input w-[120px]" type="time" value={an.night.from || NIGHT.from} onchange={(e) => setNight('from', e)} aria-label={t('Night analysis from')} />
          {t('to')}
          <input class="input w-[120px]" type="time" value={an.night.to || NIGHT.to} onchange={(e) => setNight('to', e)} aria-label={t('Night analysis until')} />
        </span>
      </Row>
    {/if}
    <details class="fold">
      <summary><Icon name="settings" size={18} />{t('Daytime and performance')}</summary>
      <div class="in grid gap-1">
        <p class="muted small">{t('Applies to runs outside the night – new music and “Update everything”: new songs first, the rest comes later. 0 = no limit.')}</p>
        <Row label={t('Time limit for measuring')}>
          <div class="btns"><NumInput obj={an} key="budgetMinutes" min={0} max={1440} placeholder="10" width={90} /><span class="muted small">{t('minutes')}</span></div>
        </Row>
        <Row label={t('Time limit for AI')}>
          <div class="btns"><NumInput obj={an} key="mlBudget" min={0} max={1440} placeholder="15" width={90} /><span class="muted small">{t('minutes')}</span></div>
        </Row>
        <Row label={t('Simultaneous measurements')} hint={t('0 = automatic: half as many as processor cores.')}>
          <NumInput obj={an} key="workers" min={0} max={32} placeholder="0" width={90} />
        </Row>
        <Row label={t('Processor cores for the AI')} hint={t('The AI may use at most this many cores – the rest stays free for Navidrome.')}>
          <NumInput obj={an} key="mlThreads" min={1} max={8} placeholder="2" width={90} />
        </Row>
      </div>
    </details>
  </Card>

  <Card title={t('Same recording twice')} icon="fingerprint">
    <p class="muted small">{t('Audio fingerprints find songs stored more than once – also as another format, in another folder or on another album, for example a FLAC file next to its converted Opus file. Live versions, re-recordings and karaoke stay apart. They are made during “Understand music” and at night, new songs first.')}</p>
    {#if !fp.available}
      <div class="small warn-t">{t('fpcalc is {why} – it is included in the Docker image.', { why: fp.why || t('not installed') })}</div>
    {:else}
      <div>
        <div class="progress my-1.5"><i style:width="{fpPct}%"></i></div>
        <div class="small">{t('{done} of {total} songs · {pct}%', { done: fmt(fp.songs || 0), total: fmt(fp.total || 0), pct: fpPct })}</div>
        {#if fpInfo}<div class="tiny muted">{fpInfo}</div>{/if}
      </div>
      {#if fp.comparedAt}
        <div class="member-row flex-wrap">   <!-- narrow: the button moves below the text -->
          <Icon name={fp.groups ? 'copy' : 'check'} size={18} class={fp.groups ? 'warn-t' : 'ok-t'} />
          <div class="flex-1 min-w-[200px]">
            <b>{fp.groups ? tn(fp.groups, '{n} recording is there more than once', '{n} recordings are there more than once') : t('No recording is there twice')}</b>
            <div class="tiny muted">{fp.groups ? tn(fp.extra, '{n} extra file · compared {when}', '{n} extra files · compared {when}', { when: serverDate(fp.comparedAt) }) : t('compared {when}', { when: serverDate(fp.comparedAt) })}</div>
          </div>
          <a class="btn sm max-mobile:ml-7" href="#/einstellungen/bibliothek">{t('Check library')}</a>
        </div>
      {/if}
    {/if}
    <Row label={t('Make audio fingerprints')} hint={t('Independent of the AI sound analysis. About 3 KB per song – not part of the backup, they renew themselves.')}>
      <Toggle obj={an} key="fingerprints" />
    </Row>
  </Card>

  <Card title="Last.fm" icon="globe">
    <p class="muted small">{t('Free with your own key: similar bands for radio, suggestions and “You might still be missing”, plus genre and mood tags for classifying new bands. Everything is cached for 30 days.')}</p>
    <div class="member-row">
      <Icon name={l.key ? 'check' : 'key'} size={18} class={l.key ? 'ok-t' : 'warn-t'} />
      <div class="flex-1 min-w-0">
        <b>{l.key ? t('Key entered') : t('No key yet')}</b>
        <div class="tiny muted">{t('{n} bands loaded', { n: fmt(l.artists || 0) }) + (l.lastRun ? t(' · last run {when}', { when: serverDate(l.lastRun) }) : '')}</div>
      </div>
    </div>
    {#if locked}
      <div class="note">{t('The key is set in docker-compose.yaml as LASTFM_API_KEY.')}</div>
    {:else}
      <div class="frow">
        <label class="f">{t('API key')}
          <input class="input w-full" type="password" autocomplete="off" bind:value={key} placeholder={env.lastfm ? t('•••••• entered') : t('API key')} />
        </label>
      </div>
      <div class="btns">
        <button class="btn" onclick={test}>{t('Test')}</button>
        <button class="btn primary" onclick={saveKey}>{t('Save')}</button>
        <div class="small {out.cls}">{out.text}</div>
      </div>
    {/if}
    <div class="hint">{t('You can get a key for free at last.fm/api/account/create. It is only stored on your NAS.')}</div>
    <Row label={t('Time limit per run')} hint={t('Tuttiphon loads Last.fm data for at most this long. The first pass takes a few minutes.')}>
      <div class="btns"><NumInput obj={an} key="lastfmBudget" min={0} max={600} placeholder="3" width={90} /><span class="muted small">{t('minutes')}</span></div>
    </Row>
  </Card>

  <Card title={t('Music worlds')} icon="globe">
    <p class="muted small">{t('From genres, Last.fm tags, AI music style, language and decade, Tuttiphon recognizes which music worlds your library offers – such as 80s hits, Eurodance, German rap or Schlager & party – and classifies every band. New bands go into their world on their own.')}</p>
    <Row label={t('Create music worlds automatically')} hint={t('From 4 bands and 60 songs, or from just 2 bands if someone listens to them a lot. Deleted worlds don’t come back.')}>
      <Toggle obj={wl} key="auto" />
    </Row>
  </Card>

  <Card title={t('Classify new bands')} icon="sparkles">
    <p class="muted small">{t('For bands without a music world, Tuttiphon works out where they fit – from similar bands on Last.fm, tags, genres, the music styles of the AI sound analysis and the scene catalog. With match rate and reasoning.')}</p>
    <Row label={t('What happens with matches')} hint={t('“Suggest” shows them under “To review” on the home page.')}>
      <Seg options={[['off', t('nothing')], ['suggest', t('suggest')], ['auto', t('automatic')]]} value={an.classify || 'suggest'} onchange={(v) => { an.classify = v; changed() }} />
    </Row>
    {#if (an.classify || 'suggest') === 'suggest'}
      <Row label={t('Classify new bands right away')} hint={t('Bands that are new in the library, e.g. from Lidarr, go straight into their music world with a confident match of 75% or more. “To review” then shows what was classified, with “Undo”.')}>
        <Toggle obj={an} key="autoNew" />
      </Row>
    {/if}
    {#if (an.classify || 'suggest') === 'auto'}
      <Row label={t('Automatic from')} hint={t('Only very confident matches are classified directly; the rest stays a suggestion.')}>
        <Select options={[[0.6, '60 %'], [0.7, '70 %'], [0.75, '75 %'], [0.8, '80 %'], [0.9, '90 %']]} value={an.autoThreshold ?? 0.75}
          onchange={(v) => { an.autoThreshold = Number(v); changed() }} />
      </Row>
    {/if}
    {#if d.classify?.length}
      <div class="grid grid-cols-[minmax(0,1fr)] gap-1.5">
        {#each d.classify.slice(0, 12) as x (x.artist)}
          <div class="member-row">
            <span class={['pill', x.score >= 0.7 ? 'ok' : x.score >= 0.5 && 'acc']}>{Math.round(x.score * 100)} %</span>
            <div class="flex-1 min-w-0">
              <b class="ell block">{x.artist} → {x.weltName}</b>
              <div class="tiny muted ell">{t('{n} songs · {why}', { n: fmt(x.songs), why: x.why })}</div>
            </div>
            <button class="btn sm" onclick={() => addTo(x)}>{t('add')}</button>
          </div>
        {/each}
      </div>
    {:else}
      <p class="muted small">{t('No bands without a music world right now.')}</p>
    {/if}
    {#if d.stile?.length}
      <Field label={t('Vibes from Last.fm tags for bands without a genre')}>
        <div class="grid grid-cols-[minmax(0,1fr)] gap-1.5">
          {#each d.stile.slice(0, 8) as x (x.artist + '|' + x.stil)}
            {@const st = S.config.stile.find((y) => y.id === x.stil)}
            <div class="member-row">
              <div class="flex-1 min-w-0">
                <b class="ell block">{x.artist} → {st?.name || x.stil}</b>
                <div class="tiny muted">{x.why}</div>
              </div>
              <button class="btn sm" onclick={() => addStil(x)}>{t('assign')}</button>
            </div>
          {/each}
        </div>
      </Field>
    {/if}
  </Card>

  <Card title={t('Run now')} icon="play">
    <div class="btns">
      <button class="btn primary sm" disabled={S.running} onclick={() => startTask(['analyse'], { analyse_full: true })}><Icon name="brain" size={15} />{t('Analyze everything without a time limit')}</button>
      <button class="btn sm" disabled={S.running} onclick={() => startTask(['analyse'])}>{t('One pass with a time limit')}</button>
    </div>
    <div class="hint">{t('Sound analysis and AI sound analysis one after the other. The first full pass takes many hours on the NAS, the AI much longer. It can be stopped at any time – the night analysis is usually enough. After that, only new songs are left.')}</div>
  </Card>
{/if}

<style>
  .stage { display: grid; grid-template-columns: 30px minmax(0, 1fr); gap: 12px; align-items: start; padding: 12px 14px; border-radius: var(--radius-small); background: var(--surface-2); }
  .num { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 99px; background: var(--accent); color: #fff; font-weight: 800; font-size: .9rem; }
</style>
