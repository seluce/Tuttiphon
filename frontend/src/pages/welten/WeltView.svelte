<!-- Music world for users: view, like, make a mix or playlist from it, see your own favorites in it –
     editing is up to the administrator. -->
<script>
  import HelpLink from '../../components/HelpLink.svelte'
  import Icon from '../../components/Icon.svelte'
  import Glyph from '../../components/Glyph.svelte'
  import Avatar from '../../components/Avatar.svelte'
  import Collage from '../../components/Collage.svelte'
  import Section from '../../components/Section.svelte'
  import PlaylistCard from '../../components/PlaylistCard.svelte'
  import { S, findPerson, defaultPerson, changed, snapshot } from '../../lib/state.svelte.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { go } from '../../lib/router.svelte.js'
  import { openArtist } from '../../lib/artist.js'
  import { fmt, plural, uid, today } from '../../lib/format.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { w, d } = $props()

  const me = $derived(findPerson(defaultPerson()))
  const liked = $derived((me?.likes?.welten || []).includes(w.id))
  const mine = $derived(d.playlists.map((p) => S.config.playlists.find((x) => x.id === p.id)).filter(Boolean))
  const myMix = $derived(me ? S.config.playlists.find((p) => p.person === me.id && p.type === 'mix' && p.welt === w.id
    && !p.radio && (p.status || 'aktiv') !== 'papierkorb') : null)

  /** Daily Mix from this world – with one tap (or go to the existing one) */
  function makeMix() {
    if (!me || !(S.me?.own || []).includes(me.id)) { go('#/willkommen'); return }   // needs an own profile first
    if (myMix) { go(`#/playlist/${encodeURIComponent(myMix.id)}`); return }
    snapshot()
    const id = uid(`${w.id}-mix`)
    S.config.playlists.push({ id, person: me.id, welt: w.id, stil: '*', type: 'mix', mix: { size: 50, perArtist: 3, every: 'day' },
      status: 'aktiv', created: today(), source: 'welt' })
    changed()
    toast(t('Daily Mix from {name} created – coming to Symfonium shortly', { name: w.name }), { undo: true })
    go(`#/playlist/${encodeURIComponent(id)}`)
  }

  function like() {
    if (!me) { go('#/willkommen'); return }
    me.likes ??= { welten: [], stile: [], artists: [] }
    const on = me.likes.welten.includes(w.id)
    me.likes.welten = on ? me.likes.welten.filter((x) => x !== w.id) : [...me.likes.welten, w.id]
    changed()
    toast(on ? t('{name} is no longer one of your favorite worlds', { name: w.name }) : t('{name} is now one of your favorite worlds – this improves your suggestions', { name: w.name }))
  }
</script>

<a href="#/welten" class="link inline-flex gap-1.5 items-center mt-2.5 mb-3.5"><Icon name="left" size={16} />{t('All music worlds')}</a>

<div class="hero">
  <div class="hero-bg" style:background-image={d.artists[0]?.[2] ? `url(/img/ar-${d.artists[0][2]}?s=300)` : undefined}></div>
  <div class="hero-row items-center">
    <div class="w-[180px]"><Collage artists={d.artists} /></div>
    <div class="hero-text">
      <div class="eyebrow">{t('Music world')}</div>
      <h1 class="flex gap-2.5 items-center"><Glyph value={w.icon} size={30} />{w.name}<HelpLink /></h1>
      <div class="hero-meta">
        <span><b>{fmt(d.memberList.length)}</b> {d.memberList.length === 1 ? t('band') : t('bands')}</span>
        <span><b>{fmt(d.songs)}</b> {d.songs === 1 ? t('song') : t('songs')}</span>
        {#if d.scene}<span class="pill acc">{d.scene.name}</span>{/if}
      </div>
      {#if d.scene?.description}<p class="muted small max-w-[560px]">{d.scene.description}</p>{/if}
      <div class="btns mt-2">
        <button class="btn white" onclick={makeMix}><Icon name="dice" size={17} />{myMix ? t('Your mix') : t('Daily Mix')}</button>
        <a class="btn" href="#/neu?welt={w.id}&step=2"><Icon name="plus" size={17} />{t('Playlist')}</a><!-- i18n-ignore: route -->
        <button class="btn" class:primary={liked} onclick={like}><Icon name="heart" size={17} />{liked ? t('Liked') : t('Like')}</button>
      </div>
    </div>
  </div>
</div>

{#if d.forMe?.bands.length}
  <Section title={t('Your favorites here')} icon="sparkles">
    <p class="muted small -mt-1.5 mb-3.5">{t('{pct}% of what you listen to comes from this world. These are the bands you play most here.', { pct: Math.max(1, Math.round(d.forMe.share * 100)) })}</p>
    <div class="agrid">
      {#each d.forMe.bands as m (m.name)}
        <button class="acard" onclick={() => openArtist(m.name)}>
          <Avatar name={m.name} id={m.id} size={84} />
          <div class="nm">{m.name}</div>
        </button>
      {/each}
    </div>
  </Section>
{/if}

<Section title={t('Bands · {n}', { n: d.memberList.length })}>
  <p class="muted small -mt-1.5 mb-3.5">{t('Tap a band to see albums, similar bands and a radio. If a band is missing or in the wrong place, let the administrator know.')}</p>
  <div class="agrid">
    {#each d.memberList as m (m.name)}
      <button class="acard" onclick={() => openArtist(m.name)}>
        <Avatar name={m.name} id={m.id} size={84} />
        <div class="nm">{m.name}</div>
        <div class="sub">{plural(m.songs, 'song', 'songs')}</div>
      </button>
    {/each}
  </div>
</Section>

{#if mine.length}
  <Section title={t('Playlists with this world')}>
    <div class="g-pl">{#each mine as p (p.id)}<PlaylistCard {p} />{/each}</div>
  </Section>
{/if}
