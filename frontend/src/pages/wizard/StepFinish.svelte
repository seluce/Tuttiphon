<!--
  Last step of the assistant: name, kind, selection, order … – next to it the preview (asks again on every change).
  d: the draft (reactive, changed directly). A mood, instrument or theme from the search (d.sound.moods,
  d.sound.instruments, d.sound.themes) can be changed here.
-->
<script>
  import { untrack } from 'svelte'
  import Icon from '../../components/Icon.svelte'
  import Field from '../../components/Field.svelte'
  import Select from '../../components/Select.svelte'
  import Mosaic from '../../components/Mosaic.svelte'
  import Avatar from '../../components/Avatar.svelte'
  import TrackList from '../../components/TrackList.svelte'
  import ArtistChips from '../../components/ArtistChips.svelte'
  import TypeField from '../../components/TypeField.svelte'
  import SoundPicker from '../../components/SoundPicker.svelte'
  import MixFields from '../../components/MixFields.svelte'
  import { S, MOODS } from '../../lib/state.svelte.js'
  import { api } from '../../lib/api.js'
  import { SORTS, AUSWAHL } from '../../lib/editor.js'
  import { openArtist } from '../../lib/artist.js'
  import { fmt, debounce, plural } from '../../lib/format.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { d } = $props()
  const noop = () => {}   // the preview follows every change to d by itself

  let nameText = $state(untrack(() => d.name) || '')
  let r = $state.raw(null)       // latest preview
  let error = $state(null)
  let suggested = $state(null)   // name the preview suggests

  const mix = $derived(d.type === 'mix')

  // mood (from the search, e.g. "calm children's songs"): shown as long as the assistant is open, even when emptied
  const withMood = untrack(() => !!d.sound?.moods?.length)
  const moods = $derived(d.sound?.moods || [])
  function toggleMood(id) {
    const next = { ...d.sound, moods: moods.includes(id) ? moods.filter((m) => m !== id) : [...moods, id] }
    if (!next.moods.length) delete next.moods
    if (Object.keys(next).length) d.sound = next
    else delete d.sound
  }
  // instruments and themes (from the search, e.g. "calm piano music", "film music"): the same, as long as the
  // assistant is open
  const withInstr = untrack(() => !!d.sound?.instruments?.length)
  const withThemes = untrack(() => !!d.sound?.themes?.length)
  function setSound(key, ids) {
    const next = { ...d.sound, [key]: ids }
    if (!ids.length) delete next[key]
    if (Object.keys(next).length) d.sound = next
    else delete d.sound
  }
  const rv = $derived(d.hits ? 'hits' : d.minRating != null ? String(d.minRating) : '')
  function setAuswahl(v) {
    delete d.hits
    delete d.minRating
    if (v === 'hits') d.hits = true
    else if (v !== '') d.minRating = Number(v)
  }

  /** Summary line of the preview (whole sentences per kind and renewal). */
  function summary(res) {
    if (!res.mix) {
      const v = { n: fmt(res.count), artists: fmt(res.artistCount), limit: res.limit }
      return res.limit && res.count > res.limit ? t('{n} songs by {artists} bands · {limit} per request, always reshuffled', v) : t('{n} songs by {artists} bands', v)
    }
    const v = { n: fmt(res.count), pool: fmt(res.pool), bands: fmt(res.artistCount) }
    const every = d.mix?.every || 'day'
    return every === 'week' ? t('This week {n} of {pool} matching songs · {bands} bands · new every week', v)
      : every === 'month' ? t('This month {n} of {pool} matching songs · {bands} bands · new every month', v)
        : t('Today {n} of {pool} matching songs · {bands} bands · new every day', v)
  }

  let seq = 0
  let alive = true
  const refresh = debounce(async (body) => {
    const mine = ++seq
    try {
      const res = await api('/api/preview', { body: { ...body, sampleSize: 8 } })
      if (mine !== seq || !alive) return
      suggested = res.name
      r = res
      error = null
    } catch (e) {
      if (mine === seq && alive) error = e.message
    }
  }, 250)
  $effect(() => {
    const body = $state.snapshot(d)   // reads everything – every change asks again
    untrack(() => refresh(body))
  })
  $effect(() => () => { alive = false })
</script>

{#snippet auswahl()}
  <label class="f">{mix ? t('From which songs?') : t('Selection')}<Select options={AUSWAHL} value={rv} onchange={setAuswahl} /></label>
{/snippet}

<div class="g-2">
  <div class="card grid gap-4">
    <label class="f">{t('Name')}<input class="input" bind:value={nameText} placeholder={suggested ?? t('automatic')} oninput={() => (d.name = nameText.trim() || undefined)} /></label>
    {#if withMood}
      <Field label={t('Mood – one of them is enough')}>
        <div class="toggles">
          {#each Object.entries(MOODS) as [id, label] (id)}
            <button type="button" class="toggle" class:on={moods.includes(id)} aria-pressed={moods.includes(id)} onclick={() => toggleMood(id)}>{label}</button>
          {/each}
        </div>
      </Field>
    {/if}
    {#if withInstr}<SoundPicker value={d.sound?.instruments || []} onchange={(ids) => setSound('instruments', ids)} />{/if}
    {#if withThemes}<SoundPicker kind="themes" value={d.sound?.themes || []} onchange={(ids) => setSound('themes', ids)} />{/if}
    <TypeField p={d} onchange={noop} />
    {#if mix}
      <div class="frow">{@render auswahl()}</div>
      <MixFields p={d} onchange={noop} />
    {:else}
      <div class="frow">
        {@render auswahl()}
        <label class="f">{t('Order')}<Select options={SORTS} value={d.sort || 'random'} onchange={(v) => (d.sort = v === 'random' ? undefined : v)} /></label>
      </div>
      <div class="frow">
        <label class="f">{t('Max. songs')}<input class="input" type="number" min="10" step="10" value={d.limit || ''} placeholder={S.config.settings.limit}
          onchange={(e) => (d.limit = e.currentTarget.value ? Number(e.currentTarget.value) : undefined)} /></label>
        <label class="f">{t('Skip recently played')}<Select options={[['', t('no')], ['7', plural(7, 'day', 'days')], ['14', plural(14, 'day', 'days')], ['30', plural(30, 'day', 'days')]]}
          value={d.notPlayedDays || ''} onchange={(v) => (d.notPlayedDays = v ? Number(v) : undefined)} /></label>
      </div>
    {/if}
    <details class="fold">
      <summary><Icon name="users" size={18} />{t('Add or leave out single bands')}</summary>
      <div class="in">
        <Field label={t('Also include')}><ArtistChips items={d.addArtists} onchange={noop} /></Field>
        <Field label={t('Never include')}><ArtistChips items={d.excludeArtists} onchange={noop} /></Field>
      </div>
    </details>
  </div>

  <div class="card grid gap-4">
    {#if error}
      <div class="err-t">{error}</div>
    {:else if !r}
      <div class="skel h-[200px]"></div>
    {:else}
      <div class="grid grid-cols-[120px_minmax(0,1fr)] gap-4 items-center">
        <Mosaic covers={r.covers} />
        <div class="min-w-0">
          <div class="eyebrow">{t('Preview')}</div>
          <h2 class="my-1">{d.name || r.name}</h2>
          <div class="muted small">
            {summary(r)}
          </div>
          {#if (r.mix ? r.pool : r.count) < 15}<div class="warn-t small">{t('Rather few – maybe “all songs” instead of only hits?')}</div>{/if}
        </div>
      </div>
      <div class="arows">
        {#each r.topArtists.slice(0, 5) as [n, c, id] (n)}
          <button class="arow w-full text-left" onclick={() => openArtist(n)}>
            <Avatar name={n} {id} size={36} />
            <b class="ell">{n}</b>
            <div class="bar"><i style:width="{(c / Math.max(1, r.topArtists[0][1])) * 100}%"></i></div>
            <span class="n">{c}</span>
          </button>
        {/each}
      </div>
      <TrackList tracks={r.sample.slice(0, 8)} from={t('Preview')} compact />
    {/if}
  </div>
</div>
