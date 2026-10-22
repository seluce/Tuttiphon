<!--
  One suggestion on "Discover": a playlist (create/customize), a new music world (scene) or "set taste".
  ✕ (top right) hides it for six months. onaccepted(): accepted – the page removes it from its list.
-->
<script>
  import Icon from '../../components/Icon.svelte'
  import Mosaic from '../../components/Mosaic.svelte'
  import Collage from '../../components/Collage.svelte'
  import PersonAvatar from '../../components/PersonAvatar.svelte'
  import { S, findPerson, findWelt, familyPerson, defaultOwner, mixWording, snapshot, changed } from '../../lib/state.svelte.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { go } from '../../lib/router.svelte.js'
  import { accept } from '../../lib/discover.js'
  import { openEditor } from '../../lib/editor.js'
  import { plEmoji } from '../../lib/playlist.js'
  import { fmt, plural, uid, today, clone } from '../../lib/format.js'
  import { t, tn } from '../../lib/i18n.svelte.js'

  let { s, onaccepted } = $props()

  function dismiss() {
    snapshot()
    S.config.dismissed.push(s.key)
    changed()
    toast(t('Suggestion hidden'), { undo: true })
  }
  function take() {
    accept(s)
    onaccepted()
  }
  function customize() {
    openEditor({ ...clone(s.playlist), id: uid(s.name), source: 'vorschlag' },
      { isNew: true, onSaved: (p) => go(`#/playlist/${encodeURIComponent(p.id)}`) })
  }
  /** New music world from a scene – including a mix playlist for it: the family's, without a family yours. */
  function acceptScene() {
    snapshot()
    let id = s.welt.id
    while (findWelt(id)) id += '-2'
    S.config.welten.push({ ...clone(s.welt), id })
    const owner = (familyPerson() || defaultOwner())?.id
    if (owner) S.config.playlists.push({ id: uid(`${id}-mix`), person: owner, welt: id, stil: '*', status: 'aktiv', created: today(), source: 'vorschlag' })
    onaccepted()
    changed()
    toast(owner ? t('{name} created – with a mix playlist', { name: s.welt.name }) : t('{name} created', { name: s.welt.name }),
      { undo: true, action: { label: t('View'), run: () => go(`#/welt/${id}`) } })
  }
  /** The small line under a playlist suggestion: for whom, hits only, size. */
  function details(p, mix) {
    const parts = [t('for {name}', { name: findPerson(p.person)?.name || '?' })]
    if (p.hits) parts.push(t('hits only'))
    if (p.review) parts.push(tn(s.count, '{n} song, changes on the first of the month', '{n} songs, changes on the first of the month'))
    else if (p.album) parts.push(t('one whole album a week, from {n} never played', { n: fmt(s.count) }))
    else if (p.episodes) parts.push(tn(s.count, 'the next episode of {n} series, new every day', 'the next episode of each of {n} series, new every day'))
    else if (mix) {
      const v = { when: mixWording(p)[1], size: p.mix?.minutes ? t('{n} minutes', { n: p.mix.minutes }) : p.mix?.size || 50, n: fmt(s.count), max: p.mix?.perArtist || 3 }
      parts.push(p.mix?.perArtist === 0 ? t('{when}: {size} from {n} songs', v) : t('{when}: {size} from {n} songs, max. {max} per band', v))
    } else parts.push(plural(s.count, 'song', 'songs'))
    return parts.join(' · ')
  }
</script>

<!-- ✕ in the top right corner of the card (the text flows around it), so the buttons keep their row;
     on the picture of a music world with a dark background -->
{#snippet x(onPicture = false)}
  <button class={['btn icon sm x', onPicture ? 'absolute top-2 right-2 z-[1] bg-black/55 text-white border-transparent hover:bg-black/70' : 'ghost float-right -mt-1.5 -mr-1.5 ml-1']}
    title={t('Not interested')} aria-label={t('Not interested')} onclick={dismiss}><Icon name="x" size={16} /></button>
{/snippet}

{#if s.kind === 'likes'}
  <div class="scard" data-guide="vorschlag">
    <PersonAvatar p={findPerson(s.person)} size={80} />
    <div class="min-w-0">
      {@render x()}
      <div class="t">{s.title}</div>
      <div class="w">{s.why}</div>
      <div class="acts"><a class="btn primary sm" href="#/person/{s.person}">{t('Set taste')}</a></div>
    </div>
  </div>
{:else if s.kind === 'scene'}
  <div class="wcard cursor-default relative">
    <Collage artists={s.topArtists} icon={s.welt.icon} title={s.welt.name} sub="{plural(s.bands.length, 'band', 'bands')} · {plural(s.count, 'song', 'songs')}" class="aspect-[3/1.25]" />
    <div class="body">
      {#if s.because}<span class="pill acc tiny w-fit"><Icon name="sparkles" size={12} />{s.because}</span>{/if}
      <div class="muted small">{s.why}</div>
      <div class="tiny muted">{s.bands.slice(0, 8).join(' · ') + (s.bands.length > 8 ? ' …' : '')}</div>
      <div class="btns">
        <button class="btn primary sm" onclick={acceptScene}><Icon name="plus" size={16} />{t('Create music world')}</button>
      </div>
    </div>
    {@render x(true)}
  </div>
{:else}
  {@const p = s.playlist}
  {@const mix = p.type === 'mix'}
  <div class="scard" data-guide="vorschlag">
    <div class="relative min-w-0">
      <Mosaic covers={s.covers} marks={plEmoji(p)} />
      {#if mix}<span class="badge-mix">{t('Mix')}</span>{/if}
    </div>
    <div class="min-w-0">
      {@render x()}
      {#if s.because}<span class="pill acc tiny mb-1"><Icon name="sparkles" size={12} />{s.because}</span>{/if}
      <div class="t">{s.title}</div>
      <div class="w">{s.why}</div>
      <div class="tiny muted mt-1">{details(p, mix)}</div>
      <div class="acts">
        <button class="btn primary sm" data-guide="anlegen" onclick={take}><Icon name="plus" size={16} />{t('Create')}</button>
        <button class="btn sm" onclick={customize}>{t('Customize')}</button>
      </div>
    </div>
  </div>
{/if}
