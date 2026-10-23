<!--
  Year recap as a story (#/jahr[/<person>[/<year>]]): slide by slide through the year of a person or the family –
  listening time, band of the year, top bands and songs, discoveries, when the music plays, music worlds – from
  /api/rueckblick?kind=jahr. Right half (or →, space) on, left third (or ←) back, Esc or × closes. The last slide shares
  the year as a picture (jahr/share.js), keeps it as a playlist and leads from the own year to the family's.
  Without a year given: in January the one just ended, otherwise the current one so far.
-->
<script>
  import { onMount } from 'svelte'
  import { fade, fly } from 'svelte/transition'
  import Icon from '../components/Icon.svelte'
  import Glyph from '../components/Glyph.svelte'
  import Avatar from '../components/Avatar.svelte'
  import Cover from '../components/Cover.svelte'
  import PersonAvatar from '../components/PersonAvatar.svelte'
  import { S, isAdmin, myPerson, familyPerson, defaultOwner, findPerson, creatablePersons } from '../lib/state.svelte.js'
  import { previous, go } from '../lib/router.svelte.js'
  import { api } from '../lib/api.js'
  import { toast } from '../lib/overlay.svelte.js'
  import { fmt } from '../lib/format.js'
  import { dayLabel } from './stats/util.js'
  import { recapYear, yearTitle, partOfDay, partText, weekdayName, busiestIndex } from './jahr/year.js'
  import { yearPicture, sharePicture } from './jahr/share.js'
  import { t, tn, tword, locale } from '../lib/i18n.svelte.js'

  let { person: wantedPerson = null, year: wantedYear = null } = $props()

  /** Whose year: the one in the address if one may see it (administrators everyone, users their own and the
   *  family's), otherwise the own one. */
  const allowed = () => (isAdmin() ? S.config.personen : [myPerson(), familyPerson()].filter(Boolean))
  let switched = $state(null)   // from the own year to the family's (and back) – in place, × still leads back
  const person = $derived(switched || allowed().find((p) => p.id === wantedPerson) || defaultOwner())
  const year = $derived(/^\d{4}$/.test(wantedYear || '') ? Number(wantedYear) : recapYear())
  const title = $derived(yearTitle(person, year))
  const family = familyPerson()

  let d = $state(null)
  let error = $state('')
  let i = $state(0)
  let seq = 0
  $effect(() => {
    const who = person?.id
    const y = year
    const mine = ++seq
    d = null
    error = ''
    i = 0
    if (!who) { error = t('No person yet – set one up under People first.'); return }
    api(`/api/rueckblick?kind=jahr&person=${encodeURIComponent(who)}&year=${y}`)
      .then((r) => { if (mine === seq) d = r })
      .catch((e) => { if (mine === seq) error = e.message })
  })

  const sum = (list) => (list || []).reduce((a, b) => a + b, 0)
  const tot = $derived(d?.totals)
  const since = $derived(d?.since && new Date(d.since) > new Date(`${year}-01-01T00:00`) ? new Date(d.since) : null)
  const hours = $derived(Math.round(tot?.hours || 0))
  const part = $derived(partOfDay(d?.hours))
  const day = $derived(busiestIndex(d?.weekdays))
  const decade = $derived(d?.decades?.length ? d.decades.reduce((a, b) => (b[1] > a[1] ? b : a))[0] : null)
  const world = $derived(d?.welten?.[0] || null)
  const maxHour = $derived(Math.max(1, ...(d?.hours || [0])))
  const hasClock = $derived(sum(d?.hours) > 0 || sum(d?.weekdays) > 0)

  /** The slides there is something to show for, in order. */
  const slides = $derived.by(() => {
    if (!tot?.plays) return []
    const out = ['intro', 'time']
    if (d.topArtists[0]) out.push('band')
    if (d.topArtists.length > 1) out.push('bands')
    if (d.topSongs[0]) out.push('songs')
    if (tot.newArtists || tot.newSongs) out.push('new')
    if (hasClock) out.push('clock')
    if (d.welten.length || decade) out.push('worlds')
    out.push('end')
    return out
  })
  const slide = $derived(slides[i])

  const next = () => { if (i < slides.length - 1) i++ }
  const back = () => { if (i > 0) i-- }
  /** Close: back to where the story was opened from – opened directly (a notification), to the start page. */
  function close() {
    if (previous() && !previous().startsWith('/jahr')) history.back()
    else go('#/')
  }

  function tap(e) {
    if (e.target.closest('button, a, input, select')) return
    const box = e.currentTarget.getBoundingClientRect()
    if (e.clientX - box.left < box.width / 3) back()
    else next()
  }
  onMount(() => {
    const key = (e) => {
      if (e.key === 'ArrowRight' || (e.key === ' ' && !e.target.closest?.('button, a'))) { e.preventDefault(); next() }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); back() }
      else if (e.key === 'Escape') close()
    }
    addEventListener('keydown', key)
    document.documentElement.classList.add('story-open')
    return () => { removeEventListener('keydown', key); document.documentElement.classList.remove('story-open') }
  })

  /** Count up to the value when the slide appears (at once with reduced motion). */
  function countUp(value) {
    return (node) => {
      const end = Number(value) || 0
      if (matchMedia('(prefers-reduced-motion: reduce)').matches || end < 10) { node.textContent = fmt(end); return }
      let frame
      const start = performance.now()
      const step = (now) => {
        const k = Math.min(1, (now - start) / 1100)
        node.textContent = fmt(Math.round(end * (1 - (1 - k) ** 3)))
        if (k < 1) frame = requestAnimationFrame(step)
      }
      frame = requestAnimationFrame(step)
      return () => cancelAnimationFrame(frame)
    }
  }

  /** "{n} hours of music" → the count big, the words beside it */
  const split = (text) => { const [before, after = ''] = text.split('{n}'); return [before.trim(), after.trim()] }

  let sharing = $state(false)
  async function share() {
    if (sharing) return
    sharing = true
    try {
      const blob = await yearPicture(d, yearTitle(person, year, true), {
        world: world ? t('World of the year: {name}', { name: world.name }) : '',
        decade: decade ? t('Most played decade: {decade}', { decade }) : '',
      })
      const how = await sharePicture(blob, `tuttiphon-${year}.png`, yearTitle(person, year, true))
      if (how === 'saved') toast(t('Picture saved'))
    } catch (e) { toast(e.message, { error: true }) } finally { sharing = false }
  }

  const canKeep = $derived(creatablePersons().some((x) => x.id === person?.id))
  let keeping = $state(false)
  async function keep() {
    keeping = true
    try {
      const r = await api('/api/rueckblick/keep', { body: { person: person.id, kind: 'jahr', year } })
      toast(tn(r.count, '“{name}” saved with {n} song – coming to Symfonium shortly', '“{name}” saved with {n} songs – coming to Symfonium shortly', { name: r.name }))
    } catch (e) { toast(e.message, { error: true }) } finally { keeping = false }
  }

  /** The other year to look at from the last slide: the own one's family, the family's own person. */
  const other = $derived(person?.family ? myPerson() : family && allowed().some((p) => p.id === family.id) ? family : null)
</script>

<div class="story" role="dialog" aria-modal="true" aria-label={title}>
  {#if slides.length}
    <div class="bars" aria-hidden="true">
      {#each slides as s, k (s)}<i class:done={k <= i}></i>{/each}
    </div>
  {/if}
  <button class="x" onclick={close} aria-label={t('Close')}><Icon name="x" size={22} /></button>

  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div class="stage s-{slide || 'empty'}" role="presentation" onclick={slides.length ? tap : undefined}>
    {#if error}
      <div class="slide" in:fade>
        <Icon name="calendar" size={44} />
        <h1>{title}</h1>
        <p class="lead">{error}</p>
        <a class="btn white" href="#/statistik/jahr">{t('To the statistics')}</a>
      </div>
    {:else if !d}
      <div class="slide" in:fade><div class="pulse"><Icon name="calendar" size={44} /></div><p class="lead">{t('Counting your plays …')}</p></div>
    {:else if !slides.length}
      <div class="slide" in:fade>
        <PersonAvatar p={person} size={84} />
        <h1>{title}</h1>
        <p class="lead">{t('Nothing has been counted for this year yet.')}</p>
        <button class="btn white" onclick={close}>{t('Close')}</button>
      </div>
    {:else}
      {#key slide + person?.id + year}
        <div class="slide" in:fly={{ y: 24, duration: 380 }} aria-live="polite">
          {#if slide === 'intro'}
            <PersonAvatar p={person} size={96} />
            <div class="eyebrow">Tuttiphon</div>
            <h1 class="huge">{title}</h1>
            <p class="lead">{since
              ? t('The year in music – counted since {date}', { date: since.toLocaleDateString(locale(), { day: 'numeric', month: 'long' }) })
              : t('The year in music')}</p>
            <button class="btn white mt-2" onclick={next}>{t('Let’s go')}<Icon name="right" size={17} /></button>
          {:else if slide === 'time'}
            {@const [before, after] = split(tword(hours, '{n} hour of music', '{n} hours of music'))}
            <div class="eyebrow">{t('Listening time')}</div>
            <div class="big">{#if before}<span class="unit">{before}</span>{/if}<b {@attach countUp(hours)}>{fmt(hours)}</b><span class="unit">{after}</span></div>
            <p class="lead">{tn(tot.plays, '{n} play', '{n} plays')} · {tn(tot.songs, '{n} different song', '{n} different songs')}</p>
            <p class="lead">{tn(tot.days, 'Music on {n} day', 'Music on {n} days')}</p>
            {#if hours >= 48}<p class="note-w">{tn(Math.round(hours / 24), '≈ {n} day non-stop', '≈ {n} days non-stop')}</p>{/if}
          {:else if slide === 'band'}
            {@const top = d.topArtists[0]}
            <div class="eyebrow">{t('Band of the year')}</div>
            <Avatar name={top.name} id={top.id} size={180} class="ring" />
            <h1>{top.name}</h1>
            <p class="lead">{t('{plays} plays from {songs} songs', { plays: fmt(top.plays), songs: fmt(top.songs) })}</p>
          {:else if slide === 'bands'}
            <div class="eyebrow">{t('Most played bands')}</div>
            <ol class="rows">
              {#each d.topArtists.slice(0, 5) as a, k (k)}
                <li style:animation-delay="{k * 90}ms"><span class="n">{k + 1}</span><Avatar name={a.name} id={a.id} size={52} /><b class="ell">{a.name}</b><span class="v">{fmt(a.plays)}×</span></li>
              {/each}
            </ol>
          {:else if slide === 'songs'}
            {@const s = d.topSongs[0]}
            <div class="eyebrow">{t('Song of the year')}</div>
            <div class="cover"><Cover id={s.cover} size={200} /></div>
            <h2>{s.title}</h2>
            <p class="lead">{s.artist} · {fmt(s.plays)}×</p>
            {#if d.topSongs.length > 1}
              <ol class="rows small">
                {#each d.topSongs.slice(1, 5) as x, k (k)}
                  <li style:animation-delay="{k * 90}ms"><span class="n">{k + 2}</span><Cover id={x.cover} size={40} /><span class="ell"><b>{x.title}</b> · {x.artist}</span><span class="v">{fmt(x.plays)}×</span></li>
                {/each}
              </ol>
            {/if}
          {:else if slide === 'new'}
            {@const [before, after] = split(tword(tot.newArtists, '{n} new band', '{n} new bands'))}
            <div class="eyebrow">{t('Newly discovered')}</div>
            {#if tot.newArtists}
              <div class="big">{#if before}<span class="unit">{before}</span>{/if}<b {@attach countUp(tot.newArtists)}>{fmt(tot.newArtists)}</b><span class="unit">{after}</span></div>
            {/if}
            {#if tot.newSongs}<p class="lead">{tn(tot.newSongs, '{n} song heard for the first time', '{n} songs heard for the first time')}</p>{/if}
            {#if d.discoveries.length}
              <div class="faces">
                {#each d.discoveries.slice(0, 6) as a, k (k)}
                  <div style:animation-delay="{k * 80}ms"><Avatar name={a.name} id={a.id} size={64} /><span class="ell">{a.name}</span></div>
                {/each}
              </div>
            {/if}
          {:else if slide === 'clock'}
            <div class="eyebrow">{t('When the music plays')}</div>
            {#if sum(d.hours)}
              <svg class="clock" viewBox="-110 -110 220 220" role="img" aria-label={partText(part)}>
                <circle r="34" class="face" />
                {#each d.hours as n, h (h)}
                  {@const a = (h / 24) * Math.PI * 2 - Math.PI / 2 + Math.PI / 24}
                  {@const len = 6 + (n / maxHour) * 58}
                  <line x1={Math.cos(a) * 40} y1={Math.sin(a) * 40} x2={Math.cos(a) * (40 + len)} y2={Math.sin(a) * (40 + len)}
                    class:top={n === maxHour} style:animation-delay="{h * 25}ms" />
                {/each}
                {#each [0, 6, 12, 18] as h (h)}
                  {@const a = (h / 24) * Math.PI * 2 - Math.PI / 2}
                  <text x={Math.cos(a) * 22} y={Math.sin(a) * 22 + 4}>{h}</text>
                {/each}
              </svg>
              <h2>{partText(part)}</h2>
            {/if}
            {#if day !== null}<p class="lead">{t('Favorite day: {day}', { day: weekdayName(day) })}</p>{/if}
            {#if d.busiest}<p class="lead">{tn(d.busiest.plays, 'The most music on {date} – {n} play', 'The most music on {date} – {n} plays', { date: dayLabel(d.busiest.day, { day: 'numeric', month: 'long' }) })}</p>{/if}
          {:else if slide === 'worlds'}
            {#if world}
              <div class="eyebrow">{t('World of the year')}</div>
              <div class="glyph"><Glyph value={world.icon || 'i:globe'} size={64} /></div>
              <h1>{world.name}</h1>
              {#if d.welten.length > 1}
                <div class="bars-h">
                  {#each d.welten.slice(0, 5) as w, k (w.id)}
                    <div style:animation-delay="{k * 90}ms"><span class="ell">{w.name}</span><i style:width="{(w.plays / d.welten[0].plays) * 100}%"></i></div>
                  {/each}
                </div>
              {/if}
            {/if}
            {#if decade}<p class="lead">{t('Most played decade: {decade}', { decade })}</p>{/if}
          {:else if slide === 'end'}
            <div class="eyebrow">{title}</div>
            <div class="summary">
              <div><b>{fmt(hours)}</b><span>{split(tword(hours, '{n} hour of music', '{n} hours of music')).join(' ').trim()}</span></div>
              <div><b>{fmt(tot.artists)}</b><span>{split(tword(tot.artists, '{n} band', '{n} bands')).join(' ').trim()}</span></div>
              {#if d.topArtists[0]}<div class="wide"><span>{t('Band of the year')}</span><b class="ell">{d.topArtists[0].name}</b></div>{/if}
              {#if d.topSongs[0]}<div class="wide"><span>{t('Song of the year')}</span><b class="ell">{d.topSongs[0].title}</b></div>{/if}
            </div>
            <div class="btns justify-center">
              <button class="btn white" disabled={sharing} onclick={share}><Icon name="share" size={17} />{sharing ? t('One moment …') : t('Share as a picture')}</button>
              {#if canKeep}<button class="btn" disabled={keeping} onclick={keep}><Icon name="pin" size={16} />{t('Keep as playlist')}</button>{/if}
            </div>
            <div class="btns justify-center">
              {#if other}
                <button class="btn ghost" onclick={() => (switched = other)}><PersonAvatar p={other} size={22} />{yearTitle(other, year)}</button>
              {/if}
              <button class="btn ghost" onclick={() => (i = 0)}><Icon name="repeat" size={16} />{t('Watch again')}</button>
            </div>
          {/if}
        </div>
      {/key}
      <div class="nav" aria-hidden="true">
        <button tabindex="-1" class="arrow" disabled={i === 0} onclick={back}><Icon name="left" size={22} /></button>
        <button tabindex="-1" class="arrow" disabled={i === slides.length - 1} onclick={next}><Icon name="right" size={22} /></button>
      </div>
    {/if}
  </div>
</div>

<style>
  .story {
    position: fixed; inset: 0; z-index: 55; color: #fff; display: grid; overflow: hidden;
    background: #1b1033;
    padding: env(safe-area-inset-top, 0px) env(safe-area-inset-right, 0px) env(safe-area-inset-bottom, 0px) env(safe-area-inset-left, 0px);
  }
  :global(html.story-open) { overflow: hidden; }
  .stage { position: relative; display: grid; place-items: center; padding: 64px 20px 76px; transition: background .5s; background: var(--story-bg); min-height: 0; overflow-y: auto; user-select: none; cursor: pointer; }
  .s-empty, .s-intro, .s-end { --story-bg: linear-gradient(150deg, #7c3aed, #c026d3 55%, #db2777); }
  .s-time { --story-bg: linear-gradient(160deg, #1e1b4b, #4c1d95 60%, #7c3aed); }
  .s-band { --story-bg: linear-gradient(160deg, #831843, #be185d 55%, #f97316); }
  .s-bands { --story-bg: linear-gradient(160deg, #0f172a, #1e3a8a 60%, #6d28d9); }
  .s-songs { --story-bg: linear-gradient(160deg, #134e4a, #0f766e 55%, #7c3aed); }
  .s-new { --story-bg: linear-gradient(160deg, #3b0764, #a21caf 55%, #f59e0b); }
  .s-clock { --story-bg: linear-gradient(160deg, #0c4a6e, #1d4ed8 60%, #9333ea); }
  .s-worlds { --story-bg: linear-gradient(160deg, #14532d, #15803d 50%, #0e7490); }

  .bars { position: absolute; top: calc(12px + env(safe-area-inset-top, 0px)); left: 16px; right: 64px; display: flex; gap: 5px; z-index: 2; }
  .bars i { flex: 1; height: 4px; border-radius: 2px; background: rgba(255, 255, 255, .3); transition: background .3s; }
  .bars i.done { background: #fff; }
  .x { position: absolute; top: calc(4px + env(safe-area-inset-top, 0px)); right: 8px; z-index: 3; width: 44px; height: 44px; display: grid; place-items: center; border-radius: 50%; color: #fff; }
  .x:hover { background: rgba(255, 255, 255, .14); }

  .slide { width: min(560px, 100%); display: grid; justify-items: center; text-align: center; gap: 14px; }
  .eyebrow { color: rgba(255, 255, 255, .78); font-size: .8rem; }
  h1 { font-size: clamp(2rem, 7vw, 3.2rem); line-height: 1.05; font-weight: 850; letter-spacing: -.02em; overflow-wrap: anywhere; }
  h1.huge { font-size: clamp(3rem, 13vw, 5.6rem); }
  h2 { font-size: clamp(1.5rem, 5vw, 2.1rem); line-height: 1.1; font-weight: 800; overflow-wrap: anywhere; }
  .lead { font-size: 1.08rem; color: rgba(255, 255, 255, .88); }
  .note-w { margin-top: 6px; padding: 10px 16px; border-radius: 999px; background: rgba(255, 255, 255, .14); font-weight: 650; }
  .big { display: flex; align-items: baseline; justify-content: center; flex-wrap: wrap; gap: 4px 14px; }
  .big b { font-size: clamp(4.4rem, 22vw, 8.5rem); line-height: .95; font-weight: 850; letter-spacing: -.04em; font-variant-numeric: tabular-nums; }
  .big .unit { font-size: 1.3rem; font-weight: 700; }
  .cover { border-radius: 18px; overflow: hidden; box-shadow: 0 20px 60px rgba(0, 0, 0, .35); }
  .slide :global(.ring) { box-shadow: 0 0 0 6px rgba(255, 255, 255, .35), 0 24px 70px rgba(0, 0, 0, .35); }
  .glyph { width: 116px; height: 116px; border-radius: 50%; display: grid; place-items: center; background: rgba(255, 255, 255, .16); }

  .rows { width: 100%; display: grid; gap: 8px; margin-top: 4px; text-align: left; }
  .rows li { display: grid; grid-template-columns: 24px auto minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 8px 12px; border-radius: 16px; background: rgba(255, 255, 255, .1); animation: rise .45s both; }
  .rows b { font-size: 1.12rem; }
  .rows.small li { padding: 6px 10px; font-size: .92rem; }
  .rows.small b { font-size: .95rem; }
  .rows .n { font-weight: 850; opacity: .7; text-align: right; }
  .rows .v { opacity: .8; font-variant-numeric: tabular-nums; }
  .faces { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px 10px; width: 100%; margin-top: 6px; }
  .faces > div { display: grid; justify-items: center; gap: 6px; font-size: .88rem; font-weight: 650; min-width: 0; animation: rise .45s both; }
  .faces .ell { max-width: 100%; }
  .bars-h { width: 100%; display: grid; gap: 8px; text-align: left; }
  .bars-h > div { position: relative; padding: 8px 14px; border-radius: 12px; overflow: hidden; background: rgba(255, 255, 255, .08); animation: rise .45s both; }
  .bars-h span { position: relative; z-index: 1; font-weight: 700; }
  .bars-h i { position: absolute; inset: 0 auto 0 0; background: rgba(255, 255, 255, .2); border-radius: 12px; }

  .clock { width: min(300px, 74vw); height: auto; overflow: visible; }
  .clock .face { fill: rgba(255, 255, 255, .1); }
  .clock line { stroke: rgba(255, 255, 255, .55); stroke-width: 6; stroke-linecap: round; animation: grow .6s both; transform-origin: 0 0; }
  .clock line.top { stroke: #fde68a; }
  .clock text { fill: rgba(255, 255, 255, .8); font-size: 11px; font-weight: 700; text-anchor: middle; }

  .summary { width: 100%; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .summary > div { display: grid; gap: 2px; padding: 14px; border-radius: 18px; background: rgba(255, 255, 255, .14); min-width: 0; }
  .summary .wide { grid-column: 1 / -1; }
  .summary b { font-size: 1.6rem; font-weight: 850; }
  .summary .wide b { font-size: 1.2rem; }
  .summary span { font-size: .85rem; color: rgba(255, 255, 255, .82); }

  .nav { position: absolute; left: 0; right: 0; bottom: 18px; display: flex; justify-content: center; gap: 14px; }
  .arrow { width: 46px; height: 46px; border-radius: 50%; display: grid; place-items: center; background: rgba(255, 255, 255, .16); color: #fff; }
  .arrow:disabled { opacity: .3; }
  .pulse { animation: pulse 1.4s ease-in-out infinite; }

  @keyframes rise { from { opacity: 0; transform: translateY(12px); } }
  @keyframes grow { from { opacity: 0; transform: scale(.6); } }
  @keyframes pulse { 50% { opacity: .45; } }
  @media (prefers-reduced-motion: reduce) {
    .rows li, .faces > div, .bars-h > div, .clock line, .pulse { animation: none; }
  }
</style>
