<!--
  Playlist editor (side sheet, opened via openEditor() in lib/editor.js): all settings of a playlist
  with a live preview. Works on a copy – only “Save” puts it into S.config.
  SheetHost draws the footer (editorFoot) below the content; it reads its state from `foot`.
-->
<script module>
  import { closeSheet } from '../../lib/overlay.svelte.js'

  // Only one sheet is open at a time – the footer belongs to the editor that is open
  const foot = $state({ label: '', hint: '', disabled: false, save: () => {} })

  export { editorFoot }
</script>

<script>
  import { untrack } from 'svelte'
  import Icon from '../Icon.svelte'
  import Glyph from '../Glyph.svelte'
  import Field from '../Field.svelte'
  import Select from '../Select.svelte'
  import Mosaic from '../Mosaic.svelte'
  import Stack from '../Stack.svelte'
  import ArtistChips from '../ArtistChips.svelte'
  import TypeField from '../TypeField.svelte'
  import MixFields from '../MixFields.svelte'
  import Switch from '../Switch.svelte'
  import SoundPicker from '../SoundPicker.svelte'
  import { narrowsLibrary } from '../../lib/sound.svelte.js'
  import { S, findPerson, defaultPerson, outOfAll, weltIds, changed, snapshot, findStil, findWelt, soundOf, mixWording,
    ownPersons, isAdmin } from '../../lib/state.svelte.js'
  import { toast, confirmDialog } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { fmt, plural, clone, uid, today, debounce } from '../../lib/format.js'
  import { SORTS, AUSWAHL, stilOptions, openEditor } from '../../lib/editor.js'
  import { t, tn } from '../../lib/i18n.svelte.js'

  let { p0, isNew = false, onSaved = null } = $props()

  function start(x) {
    const q = clone(x || {})
    q.id ??= uid('playlist')
    q.person ??= defaultPerson()
    q.welt ??= '*'
    q.stil ??= '*'
    if (!q.rules) {
      q.addArtists ??= []
      q.excludeArtists ??= []
    }
    return q
  }
  const p = $state(untrack(() => start(p0)))
  const raw = !!p.rules
  // own sound filter with instruments or themes (from the search): editable here
  const withInstr = !!p.sound?.instruments?.length
  const withThemes = !!p.sound?.themes?.length
  function setSound(key, ids) {
    const next = { ...p.sound, [key]: ids }
    if (!ids.length) delete next[key]
    if (Object.keys(next).length) p.sound = next
    else delete p.sound
  }
  const startName = p.name || ''
  const foldOpen = !raw && !!(p.addArtists.length || p.excludeArtists.length)

  let counts = $state.raw(null)
  let prev = $state.raw(null)   // { res } | { invalid } | { error }
  let auto = $state('')         // automatic name from the preview
  let hint = $state('')

  const person = $derived(findPerson(p.person || defaultPerson()))
  const ids = $derived(weltIds(p))
  const mix = $derived(p.type === 'mix')
  const rv = $derived(p.hits ? 'hits' : p.minRating != null ? String(p.minRating) : '')
  const info = $derived(S.library?.weltInfo || {})
  // Favorite bands, recap, family mix and the morning from the listening clock choose on their own – “All × Everything”
  // is right there; so is a mix whose own sound filter requires instruments or themes (e.g. “calm piano music”)
  const special = $derived(p.fav ? 'fav' : p.review ? 'review' : p.together ? 'together' : null)
  const isInvalid = () => !p.rules && !p.fav && !p.review && !p.together && !p.radio && !p.daytime && !p.unheard && !p.album && !p.episodes && !narrowsLibrary(p.sound)
    && !(p.type === 'mix' && p.mix?.flavor === 'geschmack') && weltIds(p).length === 0 && (p.stil || '*') === '*'
  const invalid = $derived(isInvalid())
  const togetherOptions = $derived(S.config.personen.filter((x) => isAdmin() || ownPersons().includes(x) || x.public))
  function toggleTogether(id) {
    const next = p.together.includes(id) ? p.together.filter((x) => x !== id) : [...p.together, id]
    if (next.length >= 2) p.together = next
  }

  // sound vibe chosen → only available as a mix
  $effect.pre(() => {
    if (soundOf(p) && p.type !== 'mix') {
      p.type = 'mix'
      p.mix ??= { size: 40, perArtist: 3, every: 'week' }
    }
  })

  foot.save = doSave
  const fresh = untrack(() => isNew)   // “Create” or “Save” as when it was opened – in the current language
  $effect.pre(() => {
    foot.label = fresh ? t('Create playlist') : t('Save')
    foot.disabled = invalid
    foot.hint = hint
  })

  const set = (k, v) => {
    if (v === '' || v == null) delete p[k]
    else p[k] = v
  }
  function toggle(id) {
    const next = ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]
    p.welt = !next.length ? '*' : next.length === 1 ? next[0] : next
  }
  function pickAuswahl(v) {
    delete p.hits
    delete p.minRating
    if (v === 'hits') p.hits = true
    else if (v !== '') p.minRating = Number(v)
  }

  // song counts per vibe – again as soon as the music world or person changes
  let countSeq = 0
  async function loadCounts() {
    const mine = ++countSeq
    let c = null
    try { c = await api('/api/counts', { body: { welt: p.welt, person: p.person, config: S.config } }) } catch { /* without numbers */ }
    if (mine !== countSeq) return   // selection changed in the meantime
    counts = c
  }
  $effect(() => {
    JSON.stringify(p.welt)
    void p.person
    if (!raw) untrack(loadCounts)
  })

  // preview at the top – on every change (slightly delayed)
  let previewSeq = 0
  const refresh = debounce(async () => {
    const mine = ++previewSeq
    const bad = isInvalid()
    hint = bad ? t('Please choose a music world or a vibe.') : ''
    if (bad) { prev = { invalid: true }; return }
    try {
      const res = await api('/api/preview', { body: { ...$state.snapshot(p), config: S.config, sampleSize: 1 } })
      if (mine !== previewSeq) return   // a newer preview is on its way
      auto = res.name
      prev = { res }
    } catch (e) { if (mine === previewSeq) prev = { error: e.message } }
  }, 250)
  $effect(() => {
    JSON.stringify(p)
    untrack(refresh)
  })

  async function convertRaw() {
    const opts = { isNew, onSaved }
    let r
    try {
      r = await api('/api/mapping', { body: { rules: p.rules, name: p.originalName || p.name, person: p.person } })
    } catch (e) {
      toast(e.message, { error: true })
      return
    }
    if (!r.mapping) { toast(t('There is no matching music world for this yet – create it under “Music worlds” first.'), { error: true }); return }
    if (!await confirmDialog(t('Switch to the builder'), t('New: {describe} – {n} songs. The playlist stays the same in Navidrome.', { describe: r.mapping.describe, n: fmt(r.mapping.count) }), t('Switch over'))) return
    const q = $state.snapshot(p)
    delete q.rules; delete q.rulesOp; delete q.sortRaw; delete q.originalName
    Object.assign(q, { welt: r.mapping.welt, stil: r.mapping.stil })
    if (r.mapping.minRating != null) q.minRating = r.mapping.minRating
    openEditor(q, opts)
  }

  let saved = false
  function doSave() {
    if (saved) return   // double click
    if (isInvalid()) { hint = t('Please choose a music world or a vibe.'); return }
    if (p.stil && p.stil !== '*' && !findStil(p.stil)) { hint = t('This vibe no longer exists – please choose another one.'); return }
    if (weltIds(p).some((w) => !findWelt(w))) {
      const ok = weltIds(p).filter((w) => findWelt(w))
      p.welt = ok.length ? ok : '*'
    }
    saved = true
    const then = onSaved   // props can no longer be read after closeSheet()
    const out = $state.snapshot(p)
    for (const k of ['addArtists', 'excludeArtists']) if (Array.isArray(out[k]) && !out[k].length) delete out[k]
    if (out.type !== 'mix') delete out.mix
    else { delete out.sort; delete out.limit; delete out.notPlayedDays }
    snapshot()
    const idx = S.config.playlists.findIndex((x) => x.id === out.id)
    if (idx >= 0 && !isNew) S.config.playlists[idx] = out
    else {
      Object.assign(out, { status: 'aktiv', created: today() })
      out.source ??= 'eigene'
      S.config.playlists.push(out)
    }
    changed()
    closeSheet()
    const name = out.name || auto || t('Playlist')
    toast(S.config.settings.autoApply !== false ? t('“{name}” saved – coming to Navidrome shortly', { name }) : t('“{name}” saved', { name }), { undo: true })
    then?.(out)
  }
</script>

{#snippet editorFoot()}
  <button class="btn primary" disabled={foot.disabled} onclick={() => foot.save()}>{foot.label}</button>
  <button class="btn ghost" onclick={closeSheet}>{t('Cancel')}</button>
  <span class="muted small">{foot.hint}</span>
{/snippet}

{#snippet auswahl()}
  <label class="f">{mix ? t('Which songs?') : t('Selection')}
    <Select options={AUSWAHL} value={rv} onchange={pickAuswahl} />
  </label>
{/snippet}

<!-- Preview -->
<div class="card flat grid grid-cols-[96px_minmax(0,1fr)] gap-4 items-center">
  {#if prev?.invalid}
    <Mosaic marks="music" />
    <div class="muted">{t('Choose below what goes into the playlist.')}</div>
  {:else if prev?.error}
    <div class="err-t col-span-2">{prev.error}</div>
  {:else if prev?.res}
    {@const res = prev.res}
    <Mosaic covers={res.covers} />
    <div class="grid gap-1.5 min-w-0">
      <h2 class="ell">{p.name || res.name}</h2>
      <div class="muted small">
        {p.album
          ? t('This week: {n} songs, one whole album out of {pool} never played', { n: fmt(res.count), pool: fmt(res.pool) })
          : p.episodes
          ? tn(res.pool, 'Today: the next episode of {n} series', 'Today: the next episode of each of {n} series')
          : res.mix
          ? t('{when}: {n} of {pool} matching songs · {bands} bands · {renew}', { when: mixWording(p)[0], n: fmt(res.count), pool: fmt(res.pool), bands: fmt(res.artistCount), renew: mixWording(p)[1] })
          : res.limit && res.count > res.limit
            ? t('{n} matching songs by {artists} bands · Navidrome shuffles {limit} of them on every load', { n: fmt(res.count), artists: fmt(res.artistCount), limit: res.limit })
            : t('{n} matching songs by {artists} bands', { n: fmt(res.count), artists: fmt(res.artistCount) })}
      </div>
      {#if !p.album && !p.episodes && (res.mix ? res.pool : res.count) < 15}
        <div class="warn-t small">{t('Rather few – maybe a lower selection or more music worlds?')}</div>
      {/if}
      <div class="flex gap-2.5 items-center min-w-0">
        <Stack artists={res.topArtists} n={6} size={30} />
        <span class="tiny muted ell min-w-0">{res.topArtists.slice(0, 3).map((a) => a[0]).join(', ')}</span>
      </div>
    </div>
  {/if}
</div>

<!-- Settings (changes to p trigger the preview by themselves) -->
<div class="grid gap-[18px]">
  <label class="f">{t('Name')}
    <input class="input" value={startName} placeholder={auto || t('automatic')} oninput={(e) => set('name', e.currentTarget.value.trim())} />
  </label>

  {#if ownPersons().length > 1}
    <Field label={t('For whom?')}>
      <div class="seg">
        {#each ownPersons() as x (x.id)}
          <button type="button" class:on={(p.person || defaultPerson()) === x.id} onclick={() => (p.person = x.id)}>
            <Glyph value={x.icon} size={15} class="mr-1.5" />{x.name}
          </button>
        {/each}
      </div>
      <div class="hint">
        {isAdmin()
          ? person?.public
            ? t('Belongs to “{user}” in Navidrome, whose stars & favorites count · visible to everyone', { user: person?.user })
            : t('Belongs to “{user}” in Navidrome, whose stars & favorites count · private', { user: person?.user })
          : person?.public ? t('Visible to everyone – your stars & favorites count.') : t('Visible only to you – your stars & favorites count.')}
      </div>
    </Field>
  {/if}

  {#if special === 'review'}
    <div class="note">{t('This playlist shows the most played songs – from what is played in Symfonium. It changes on its own on the first of the month; it always stays one playlist.')}</div>
    <div class="frow">
      <label class="f">{t('Period')}
        <Select options={[['month', t('the last month')], ['year', t('the year so far')]]} value={p.review.period || 'month'}
          onchange={(v) => (p.review = { ...p.review, period: v })} />
      </label>
      <label class="f">{t('Songs')}
        <Select options={[['25', '25'], ['50', '50'], ['100', '100']]} value={String(p.mix?.size || 50)}
          onchange={(v) => (p.mix = { ...p.mix, size: Number(v) })} />
      </label>
    </div>
  {:else if special === 'fav'}
    <div class="note">{t('Takes what is new from the favorite bands – those picked by hand and those played most.')}</div>
    <label class="f">{t('How long does something count as new?')}
      <Select options={[['30', plural(30, 'day', 'days')], ['60', plural(2, 'month', 'months')], ['90', plural(3, 'month', 'months')], ['180', t('half a year')]]} value={String(p.fav.days || 60)}
        onchange={(v) => (p.fav = { ...p.fav, days: Number(v) })} />
    </label>
  {:else if p.album}
    <div class="note">{t('Album of the week: one whole album this account has never played, picked by its taste – favorite bands first – in album order. New every Monday; during the week it stays the same.')}</div>
  {:else if p.episodes}
    <div class="note">{t('Next episode: for every audio play series this account listened to in the last 3 months, the episode that comes next – the rest of the one begun, otherwise the next one never heard. New every day; the series heard last come first.')}</div>
  {:else if raw}
    <div class="note">
      {t('This playlist still has its own rules, taken over unchanged. You can change name, person, count and order – or switch it to the builder, then everything can be set.')}
      <div class="mt-2.5"><button class="btn sm" onclick={convertRaw}><Icon name="wand" size={16} />{t('Switch to the builder …')}</button></div>
    </div>
  {:else}
    {#if special === 'together'}
      <Field label={t('What everyone likes – whose taste counts?')}>
        <div class="toggles">
          {#each togetherOptions as x (x.id)}
            <button type="button" class="toggle" class:on={p.together.includes(x.id)} onclick={() => toggleTogether(x.id)}>
              <Glyph value={x.icon} size={15} class="mr-1.5" />{x.name}
            </button>
          {/each}
        </div>
        <div class="hint">{t('Songs everyone likes come up more often. Everyone’s dislikes count.')}</div>
      </Field>
    {:else}
      <TypeField {p} onchange={() => {}} />
    {/if}
    {#if withInstr}<SoundPicker value={p.sound?.instruments || []} onchange={(ids) => setSound('instruments', ids)} />{/if}
    {#if withThemes}<SoundPicker kind="themes" value={p.sound?.themes || []} onchange={(ids) => setSound('themes', ids)} />{/if}
    <Field label={t('Music world – who plays? You can pick several.')}>
      <div class="toggles">
        <button type="button" class="toggle" class:on={!ids.length} onclick={() => (p.welt = '*')}><Glyph value="globe" size={15} class="mr-1.5" />{t('All')}</button>
        {#each S.config.welten as w (w.id)}
          <button type="button" class="toggle" class:on={ids.includes(w.id)} onclick={() => toggle(w.id)}>
            <Glyph value={w.icon} size={15} class="mr-1.5" />{w.name}
            {#if info[w.id]}<span class="n">{fmt(info[w.id].songs)}</span>{/if}
          </button>
        {/each}
      </div>
      {#if !ids.length && (outOfAll(person).length || !person?.child)}
        <div class="hint">{t('“All” = the whole library without {worlds}.', { worlds: outOfAll(person).map((w) => w.name).join(', ') || t('separate worlds') })}</div>
      {/if}
    </Field>
    <label class="f">{t('Vibe – what plays?')}
      <Select options={stilOptions(counts, ids.length > 0)} value={p.stil} onchange={(v) => set('stil', v)} />
    </label>
    {#if mix}
      {#if p.unheard}
        <div class="note">{t('Only songs this account has never played – what sounds like its taste comes much more often. New every week by default, at most one song per album.')}</div>
      {/if}
      {#if p.daytime === 'morning'}
        <div class="note">{t('Made for the mornings: starts calm and gets livelier, and songs that sound like what is played in the morning come more often. The length fits the usual morning round.')}</div>
      {/if}
      <div class="frow">{@render auswahl()}</div>
      <MixFields {p} onchange={() => {}} />
    {:else}
      <div class="frow">
        {@render auswahl()}
        <label class="f">{t('Skip recently played')}
          <Select options={[['', t('no')], ['7', t('last {n} days', { n: 7 })], ['14', t('last {n} days', { n: 14 })], ['30', t('last {n} days', { n: 30 })]]} value={p.notPlayedDays || ''}
            onchange={(v) => set('notPlayedDays', v ? Number(v) : null)} />
        </label>
      </div>
    {/if}
  {/if}

  {#if !mix && special !== 'review'}
    <div class="frow">
      <label class="f">{t('Order')}
        <Select options={SORTS} value={p.sort || 'random'} onchange={(v) => set('sort', v === 'random' ? null : v)} />
      </label>
      <label class="f">{t('Max. songs')}
        <input class="input" type="number" min="10" max="5000" step="10" value={p.limit || ''} placeholder={S.config.settings.limit}
          onchange={(e) => set('limit', e.currentTarget.value ? Number(e.currentTarget.value) : null)} />
      </label>
    </div>
  {/if}

  {#if !raw && findStil(p.stil)?.season && S.config.settings.seasonRest !== false}
    <Switch checked={!!p.yearRound} onchange={(v) => { if (v) p.yearRound = true; else delete p.yearRound }}
      label={t('All year in Symfonium, not just in season')} />
  {/if}

  {#if !raw && special !== 'review'}
    <details class="fold" open={foldOpen}>
      <summary><Icon name="users" size={18} />{t('Add or remove individual bands')}</summary>
      <div class="in">
        <Field label={t('Also include')}><ArtistChips items={p.addArtists} onchange={() => {}} /></Field>
        <Field label={t('Never in this playlist')}><ArtistChips items={p.excludeArtists} onchange={() => {}} /></Field>
      </div>
    </details>
  {/if}
</div>
