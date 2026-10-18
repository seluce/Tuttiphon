<!--
  Head of the playlist page: picture, kind & person, numbers, notes and the actions (by status and rights).
  Active own playlist: "Edit" (and "Reshuffle" for mixes) as buttons, the other actions in the "…" menu.
-->
<script>
  import HelpLink from '../../components/HelpLink.svelte'
  import Icon from '../../components/Icon.svelte'
  import Mosaic from '../../components/Mosaic.svelte'
  import PlaylistArt from '../../components/PlaylistArt.svelte'
  import StatePill from '../../components/StatePill.svelte'
  import { plStatus, findPerson, defaultPerson, canEdit } from '../../lib/state.svelte.js'
  import { openSheet, closeSheet } from '../../lib/overlay.svelte.js'
  import { plEmoji } from '../../lib/playlist.js'
  import { fmt, plural } from '../../lib/format.js'
  import { t, locale } from '../../lib/i18n.svelte.js'
  import { openEditor } from '../../lib/editor.js'
  import { MIXEVERY, setStatus, purge, duplicate, snapshotMix, reroll, coverSheet } from './actions.js'

  /** p: playlist from S.config · d: /api/playlist · onreload: reload the data (after a new cover) */
  let { p, d, onreload } = $props()

  const st = $derived(plStatus(p.id) || {})
  const person = $derived(findPerson(p.person || defaultPerson()))
  const status = $derived(p.status || 'aktiv')
  const mix = $derived(p.type === 'mix')
  const every = $derived(MIXEVERY[p.mix?.every || 'day'])
  // someone else's shared playlist: view and copy only
  const own = $derived(d.own !== false && canEdit(p))
  const nav = $derived(d.navidrome)
  const eyebrow = $derived([
    p.review ? t('Recap · changes on the first of the month') : mix ? every.eyebrow : p.rules ? t('Taken-over smart playlist') : t('Smart playlist'),
    t('for {name}', { name: person?.name || '?' }),
    // in the trash it is in no one's Navidrome – the state pill says so
    status === 'papierkorb' ? null : person?.public ? t('visible to everyone') : t('private'),
  ].filter(Boolean).join(' · '))
  const tint = $derived(d.color
    ? `linear-gradient(160deg, color-mix(in srgb, ${d.color} 55%, var(--surface)) 0%, color-mix(in srgb, ${d.color} 22%, var(--surface)) 50%, var(--surface) 100%)`
    : null)
  const cover = () => coverSheet(p, d, onreload)
  // a fixed copy of the current selection – for a mix "keep", for a smart playlist "save as fixed playlist"
  const keepLabel = $derived(mix ? t('Keep this mix') : t('Save as fixed playlist'))
  const more = () => openSheet({ title: d.name, body: moreBody })
</script>

<!-- text: translated template with {n}; value is shown in bold in its place -->
{#snippet bold(text, value)}{@const [before, after = ''] = text.split('{n}')}{before}<b>{value}</b>{after}{/snippet}

{#snippet art()}
  {#if st.cover}
    <PlaylistArt {p} {st} size={600} />
  {:else}
    <Mosaic covers={d.covers} marks={plEmoji(p)} size={300} />
  {/if}
{/snippet}

{#snippet navLink()}
  {#if nav}
    <a class="btn" href="{d.webUrl}/app/#/playlist/{nav.id}/show" target="_blank" rel="noopener"><Icon name="external" size={17} />{t('Open in Navidrome')}</a>
  {/if}
{/snippet}

{#snippet trash()}
  <button class="btn icon danger" title={t('Move to trash')} aria-label={t('Move to trash')} onclick={() => setStatus(p, 'papierkorb')}><Icon name="trash" size={18} /></button>
{/snippet}

<!-- "…" menu: the actions next to "Edit" – otherwise they wrap into several rows on the phone -->
{#snippet entry(icon, label, run, cls = '')}
  <button class="member-row p-3.5 w-full text-left {cls}" onclick={() => { closeSheet(); run() }}><Icon name={icon} /><b>{label}</b></button>
{/snippet}
{#snippet moreBody()}
  <div class="grid gap-2">
    {@render entry('image', t('Cover'), cover)}
    {@render entry('pause', t('Pause playlist'), () => setStatus(p, 'pausiert'))}
    {@render entry('pin', keepLabel, () => snapshotMix(p, d))}
    {@render entry('copy', t('Duplicate'), () => duplicate(p, d))}
    {#if nav}
      <a class="member-row p-3.5 no-underline" href="{d.webUrl}/app/#/playlist/{nav.id}/show" target="_blank" rel="noopener" onclick={closeSheet}><Icon name="external" /><b>{t('Open in Navidrome')}</b></a>
    {/if}
    {@render entry('trash', t('Move to trash'), () => setStatus(p, 'papierkorb'), 'text-err')}
  </div>
{/snippet}

<div class="hero" style:background={tint}>
  <div class="hero-bg" style:background-image={d.covers[0] ? `url(/img/${d.covers[0]}?s=300)` : null}></div>
  <div class="hero-row">
    {#if st.cover && own && status === 'aktiv'}
      <button type="button" class="hero-art block p-0 border-0 bg-transparent text-left cursor-pointer" title={t('Change cover')} onclick={cover}>{@render art()}</button>
    {:else}
      <div class="hero-art">{@render art()}</div>
    {/if}
    <div class="hero-text">
      <div class="eyebrow">{eyebrow}</div>
      <h1>{d.name}<HelpLink /></h1>
      <div class="hero-meta">
        <StatePill state={st.state || d.state || status} />
        {#if st.back}<span class="muted">{t('back in Symfonium from {date}', { date: new Date(st.back + 'T00:00').toLocaleDateString(locale(), { day: 'numeric', month: 'long' }) })}</span>{/if}
        {#if mix}
          <span>{@render bold(every.songs, fmt(d.count))}</span>
          <span>{t('from {n} matching', { n: fmt(d.pool) })}</span>
        {:else}
          <span>{@render bold(t('{n} matching songs'), fmt(d.count))}</span>
        {/if}
        <span>{plural(d.artistCount, 'band', 'bands')}</span>
        {#if !mix && d.limit}<span>{t('up to {n} per request', { n: d.limit })}</span>{/if}
        {#if nav}<span class="muted">{t('in Navidrome: {owner}', { owner: nav.owner })}</span>{/if}
      </div>
      {#if (mix ? d.pool : d.count) < 15 && status === 'aktiv'}
        <div class="warn-t small">{t('Rather few songs – maybe loosen the selection or add more music worlds.')}</div>
      {/if}
      {#if mix && !p.review && !p.mix?.minutes && (p.mix?.perArtist ?? 3) > 0 && d.count < (p.mix?.size || 50) && d.pool >= 15 && status === 'aktiv'}
        <div class="muted small">{t('The mix is shorter than wanted because at most {n} songs per band are allowed – more bands from other music worlds make it longer.', { n: p.mix?.perArtist ?? 3 })}</div>
      {/if}
      {#if !own}
        <div class="small flex gap-2.5 items-center px-3.5 py-3 rounded-card bg-surface-2 text-text-2">
          <Icon name="eye" size={18} />
          <span>{person?.name
            ? t('This playlist belongs to {name} and is shared with everyone. You can listen to it in Symfonium – or create your own version with “Copy for me” and adjust it.', { name: person.name })
            : t('This playlist belongs to someone else and is shared with everyone. You can listen to it in Symfonium – or create your own version with “Copy for me” and adjust it.')}</span>
        </div>
      {/if}
      <div class="btns mt-2.5" data-guide="pl-actions">
        {#if !own}
          <button class="btn white" onclick={() => duplicate(p, d)}><Icon name="copy" size={17} />{t('Copy for me')}</button>
          {@render navLink()}
        {:else if status === 'aktiv'}
          <button class="btn white" onclick={() => openEditor(p)}><Icon name="edit" size={17} />{t('Edit')}</button>
          {#if mix && !p.review}<button class="btn" onclick={() => reroll(p)}><Icon name="dice" size={17} />{t('Reshuffle')}</button>{/if}
          <button class="btn icon" title={t('More')} aria-label={t('More')} aria-haspopup="dialog" onclick={more}><Icon name="more" size={18} /></button>
        {:else if status === 'pausiert'}
          <button class="btn white" onclick={() => setStatus(p, 'aktiv')}><Icon name="play" size={17} />{t('Reactivate')}</button>
          <button class="btn" onclick={() => openEditor(p)}><Icon name="edit" size={17} />{t('Edit')}</button>
          {@render trash()}
        {:else}
          <button class="btn white" onclick={() => setStatus(p, 'aktiv')}><Icon name="undo" size={17} />{t('Restore')}</button>
          <button class="btn danger" onclick={() => purge(p)}><Icon name="trash" size={17} />{t('Delete permanently')}</button>
        {/if}
      </div>
    </div>
  </div>
</div>
