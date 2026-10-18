<!-- Search in the header: artists, playlists, music worlds, people – plus songs, AI styles, moods, AI instruments,
     AI themes and lyrics from the server (/api/search). The "/" key jumps into it. -->
<script>
  import Icon from '../components/Icon.svelte'
  import Avatar from '../components/Avatar.svelte'
  import Glyph from '../components/Glyph.svelte'
  import Mosaic from '../components/Mosaic.svelte'
  import PersonAvatar from '../components/PersonAvatar.svelte'
  import { S, ownPersons, plStatus, isAdmin } from '../lib/state.svelte.js'
  import { plName, plEmoji } from '../lib/playlist.js'
  import { go } from '../lib/router.svelte.js'
  import { openArtist } from '../lib/artist.js'
  import { openSong } from '../lib/song.js'

  /** Search hit as a song for the song sheet */
  const asTrack = (x) => ({ id: x.id, title: x.title, artist: x.artist, album: x.album, cover: x.albumId ? `al-${x.albumId}` : null })
  import { fmt, plural, capitalize } from '../lib/format.js'
  import { api } from '../lib/api.js'
  import { tour } from '../lib/tour.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  // icon per theme of the AI (ml.THEMES) in the result list
  const THEME_ICONS = { christmas: 'xmas', film: 'disc', epic: 'crown', dark: 'moon', love: 'heart', romantic: 'flower',
    ballad: 'mic', summer: 'palm', space: 'rocket' }

  let q = $state('')
  let sel = $state(0)
  let open = $state(false)
  let input
  const uid = $props.id()   // ids for the result list (screen readers: combobox with a list of options)
  const listId = `${uid}-results`
  const shown = $derived(open && !!q.trim())

  // Only the server knows songs, styles and moods – ask shortly after typing
  let extra = $state.raw({ songs: [], styles: [], moods: [], instruments: [], themes: [], combos: [], lyrics: [] })
  let timer, asked = ''
  $effect(() => {
    const s = q.trim()
    clearTimeout(timer)
    if (s.length < 2) { asked = ''; extra = { songs: [], styles: [], moods: [], instruments: [], themes: [], combos: [], lyrics: [] }; return }
    timer = setTimeout(() => {
      asked = s
      api(`/api/search?q=${encodeURIComponent(s)}`).then((r) => { if (asked === s) extra = r }).catch(() => {})
    }, 250)
  })

  /** Combined search ("calm children's songs", "calm piano music"), an instrument or a theme: open the assistant's
   *  last step with the preview – nothing is created yet */
  function openCombo(c) {
    if (!isAdmin() && !(S.me?.own || []).length) { go('#/willkommen'); return }   // an own profile first
    const pl = c.playlist
    // how often the mix renews itself: as the search row says (“new every week”)
    const args = new URLSearchParams({ type: 'mix', step: '3', name: c.title, every: pl.mix?.every || 'week' })
    if (pl.person) args.set('person', pl.person)
    if (pl.welt && pl.welt !== '*') args.set('welt', [pl.welt].flat().join(','))
    if (pl.stil && pl.stil !== '*') args.set('stil', pl.stil)
    if (pl.sound?.moods?.length) args.set('mood', pl.sound.moods.join(','))
    if (pl.sound?.instruments?.length) args.set('instr', pl.sound.instruments.join(','))
    if (pl.sound?.themes?.length) args.set('theme', pl.sound.themes.join(','))
    go(`#/neu?${args}`)   // i18n-ignore: route
  }

  const groups = $derived.by(() => {
    const s = q.trim().toLowerCase()
    if (!s || !S.config) return []
    const arts = (S.library?.artists || []).filter(([a]) => a.toLowerCase().includes(s))
      .sort((x, y) => (y[0].toLowerCase().startsWith(s) - x[0].toLowerCase().startsWith(s)) || y[1] - x[1]).slice(0, 6)
    const out = []
    if (extra.combos?.length) out.push({ title: t('Create as mix'), items: extra.combos.map((c) => ({ kind: 'combo', c, pick: () => openCombo(c) })) })
    if (arts.length) out.push({ title: t('Bands'), items: arts.map(([a, n, id]) => ({ kind: 'artist', a, n, id, pick: () => openArtist(a) })) })
    const pls = S.config.playlists.filter((p) => p.status !== 'papierkorb' && plName(p).toLowerCase().includes(s)).slice(0, 5)
    if (pls.length) out.push({ title: t('Playlists'), items: pls.map((p) => ({ kind: 'pl', p, pick: () => go(`#/playlist/${encodeURIComponent(p.id)}`) })) })
    const wel = S.config.welten.filter((w) => w.name.toLowerCase().includes(s)).slice(0, 4)
    if (wel.length) out.push({ title: t('Music worlds'), items: wel.map((w) => ({ kind: 'welt', w, pick: () => go(`#/welt/${w.id}`) })) })
    const per = ownPersons().filter((p) => p.name.toLowerCase().includes(s)).slice(0, 3)
    if (per.length) out.push({ title: t('People'), items: per.map((p) => ({ kind: 'person', p, pick: () => go(`#/person/${p.id}`) })) })
    if (extra.moods.length) out.push({ title: t('Mood'), items: extra.moods.map((m) => ({ kind: 'mood', m,
      pick: () => go(m.stil ? `#/neu?stil=${encodeURIComponent(m.stil)}&type=mix&step=1` : '#/neu') })) })   // i18n-ignore: route
    // instrument (AI): a mix of the whole library with it as the playlist's own sound filter
    if (extra.instruments?.length) out.push({ title: t('Instruments'), items: extra.instruments.map((x) => ({ kind: 'instr', x,
      pick: () => openCombo({ title: capitalize(x.label), playlist: { sound: { instruments: x.ids } } }) })) })
    // theme (AI): likewise – unless a vibe stands for it (“Christmas”): then the assistant with that vibe
    if (extra.themes?.length) out.push({ title: t('Themes'), items: extra.themes.map((x) => ({ kind: 'theme', x,
      pick: () => (x.stil ? go(`#/neu?stil=${encodeURIComponent(x.stil)}&type=mix&step=1`)   // i18n-ignore: route
        : openCombo({ title: capitalize(x.label), playlist: { sound: { themes: x.ids } } })) })) })
    if (extra.styles.length) out.push({ title: t('Sounds like'), items: extra.styles.map((st) => ({ kind: 'style', st,
      pick: () => openArtist(st.bands[0].name) })) })
    if (extra.songs.length) out.push({ title: t('Songs'), items: extra.songs.map((x) => ({ kind: 'song', x, pick: () => openSong(asTrack(x)) })) })
    if (extra.lyrics?.length) out.push({ title: t('In the lyrics'), items: extra.lyrics.map((x) => ({ kind: 'lyric', x, pick: () => openSong(asTrack(x)) })) })
    return out
  })
  const flat = $derived(groups.flatMap((g) => g.items))

  function close() {
    open = false
    q = ''
    input?.blur()
  }
  function choose(item) {
    close()
    item.pick()
  }
  function keydown(e) {
    if (e.key === 'ArrowDown') { if (open) sel = Math.min(sel + 1, flat.length - 1); open = true; e.preventDefault() }
    else if (e.key === 'ArrowUp') { sel = Math.max(sel - 1, 0); e.preventDefault() }
    else if (e.key === 'Enter' && shown && flat[sel]) choose(flat[sel])
    else if (e.key === 'Escape') close()
  }
  // the chosen entry stays visible in the list (arrow keys)
  $effect(() => {
    if (shown) document.getElementById(`${listId}-${sel}`)?.scrollIntoView({ block: 'nearest' })
  })
  function globalKey(e) {
    if (e.key === '/' && !tour.active && !/input|textarea|select/i.test(document.activeElement?.tagName || '')) {
      e.preventDefault()
      input?.focus()
    }
  }
</script>

<svelte:window onkeydown={globalKey} />

<div class="search" data-tour="search">
  <Icon name="search" size={18} />
  <input bind:this={input} bind:value={q} placeholder={t('Bands, songs, mood, lyric line …')} autocomplete="off" aria-label={t('Search')}
    role="combobox" aria-autocomplete="list" aria-controls={listId} aria-expanded={shown}
    aria-activedescendant={shown && flat[sel] ? `${listId}-${sel}` : undefined}
    oninput={() => { sel = 0; open = true }} onkeydown={keydown} onblur={() => setTimeout(() => (open = false), 150)} />
  {#if shown}
    <div class="search-results" id={listId} role="listbox" aria-label={t('Search results')}>
      {#each groups as g, gi (g.title)}
        <div role="group" aria-labelledby="{listId}-g{gi}">
          <div class="sr-group" id="{listId}-g{gi}">{g.title}</div>
          {#each g.items as item (item)}
            {@const i = flat.indexOf(item)}
            <div class="sr-item" class:sel={i === sel} role="option" aria-selected={i === sel} tabindex="-1" id="{listId}-{i}"
              onmousedown={(e) => { e.preventDefault(); choose(item) }}>
              {#if item.kind === 'artist'}
                <Avatar name={item.a} id={item.id} size={34} />
                <div class="ell"><div>{item.a}</div><div class="tiny muted">{plural(item.n, 'song', 'songs')}</div></div>
              {:else if item.kind === 'pl'}
                {@const st = plStatus(item.p.id)}
                <div class="w-[34px] shrink-0"><Mosaic covers={st?.covers || []} marks={plEmoji(item.p)} size={34} /></div>
                <div class="ell"><div>{plName(item.p)}</div><div class="tiny muted">{st?.count != null ? plural(st.count, 'song', 'songs') : ''}</div></div>
              {:else if item.kind === 'combo'}
                <div class="grid place-items-center shrink-0 size-[34px] rounded-full bg-accent text-white"><Icon name="dice" size={18} /></div>
                <div class="ell"><div>{item.c.title}</div><div class="tiny muted">{t('Mix · {n} matching songs, new every week', { n: fmt(item.c.count) })}</div></div>
              {:else if item.kind === 'mood'}
                <div class="grid place-items-center shrink-0 size-[34px] rounded-full bg-surface-3 text-accent"><Icon name="waves" size={18} /></div>
                <div class="ell"><div>{item.m.label}</div><div class="tiny muted">{item.m.stil ? t('{songs} · create as mix', { songs: plural(item.m.count, 'song', 'songs') }) : plural(item.m.count, 'song', 'songs')}</div></div>
              {:else if item.kind === 'instr'}
                <div class="grid place-items-center shrink-0 size-[34px] rounded-full bg-surface-3 text-accent"><Icon name="piano" size={18} /></div>
                <div class="ell"><div>{capitalize(item.x.label)}</div><div class="tiny muted">{t('{songs} · create as mix', { songs: plural(item.x.count, 'song', 'songs') })}</div></div>
              {:else if item.kind === 'theme'}
                <div class="grid place-items-center shrink-0 size-[34px] rounded-full bg-surface-3 text-accent"><Icon name={THEME_ICONS[item.x.id] || 'sparkles'} size={18} /></div>
                <div class="ell"><div>{item.x.stilName || capitalize(item.x.label)}</div><div class="tiny muted">{t('{songs} · create as mix', { songs: plural(item.x.count, 'song', 'songs') })}</div></div>
              {:else if item.kind === 'style'}
                <Avatar name={item.st.bands[0].name} id={item.st.bands[0].id} size={34} />
                <div class="ell"><div>{item.st.style}</div><div class="tiny muted ell">{item.st.bands.map((b) => b.name).join(', ')}</div></div>
              {:else if item.kind === 'song'}
                <Avatar name={item.x.artist} id={item.x.artistId} size={34} />
                <div class="ell"><div class="ell">{item.x.title}</div><div class="tiny muted ell">{item.x.artist} · {item.x.album}</div></div>
              {:else if item.kind === 'lyric'}
                <Avatar name={item.x.artist} id={item.x.artistId} size={34} />
                <div class="ell"><div class="ell">{item.x.title} <span class="muted">· {item.x.artist}</span></div><div class="tiny muted ell">{t('“{line}”', { line: item.x.line })}</div></div>
              {:else if item.kind === 'welt'}
                <div class="grid place-items-center shrink-0 size-[34px] rounded-full bg-surface-3 text-accent"><Glyph value={item.w.icon} size={18} /></div>
                <div>{item.w.name}</div>
              {:else}
                <PersonAvatar p={item.p} size={34} />
                <div>{item.p.name}</div>
              {/if}
            </div>
          {/each}
        </div>
      {:else}
        <div class="sr-item muted" role="option" aria-selected="false" aria-disabled="true">{t('Nothing found – try a band, a song or a mood like “calm”.')}</div>
      {/each}
    </div>
  {/if}
</div>
