<!--
  Welcome assistant for everyone signed in with a Navidrome account: create the account's one profile, choose a taste,
  first playlists – step by step. The profile is only created in step 4 ("Save profile & show suggestions"); until then
  everything is collected locally. The local administrator (no Navidrome account) goes to People instead.
-->
<script>
  import { untrack } from 'svelte'
  import { SvelteSet } from 'svelte/reactivity'
  import Icon from '../components/Icon.svelte'
  import Avatar from '../components/Avatar.svelte'
  import Collage from '../components/Collage.svelte'
  import Mosaic from '../components/Mosaic.svelte'
  import PersonAvatar from '../components/PersonAvatar.svelte'
  import GlyphPicker from '../components/GlyphPicker.svelte'
  import ArtistChips from '../components/ArtistChips.svelte'
  import ChipEditor from '../components/ChipEditor.svelte'
  import Field from '../components/Field.svelte'
  import TipCards from './welcome/TipCards.svelte'
  import { S, findPerson, myPerson, isAdmin, changed, save, loadLibrary } from '../lib/state.svelte.js'
  import { toast } from '../lib/overlay.svelte.js'
  import { go, replace } from '../lib/router.svelte.js'
  import { api } from '../lib/api.js'
  import { plEmoji } from '../lib/playlist.js'
  import { startTour } from '../lib/tour.svelte.js'
  import { uid, slug, today, clone, plural } from '../lib/format.js'
  import { t, tn } from '../lib/i18n.svelte.js'
  import { smooth } from '../lib/motion.js'

  const COLORS = ['#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#3b82f6', '#ef4444', '#14b8a6', '#6366f1']
  const STEPS = ['Hello', 'Profile', 'Music worlds', 'Favorite bands', 'Dislikes', 'Playlists', 'Done']   // only the count is shown
  const LAST = STEPS.length - 1
  const noop = () => {}

  const me = S.me || {}
  // only for a Navidrome account – the local administrator adds people under People (replacing: "back" must not lead here)
  const local = !me.user || !!me.notfall
  $effect(() => {
    if (local) untrack(() => replace('#/personen'))
  })
  const existing = myPerson()
  const start = existing ? clone(existing) : {
    id: '', name: me.name || me.user || '', icon: 'i:music', color: COLORS[Math.floor(Math.random() * COLORS.length)], user: me.user,
    prefix: '', likes: { welten: [], stile: [], artists: [] }, dislikes: { artists: [], genres: [] },
  }
  start.likes ??= { welten: [], stile: [], artists: [] }
  start.dislikes ??= { artists: [], genres: [] }
  const p = $state(start)

  let step = $state(0)
  let sugg = $state.raw(null)
  const picks = new SvelteSet()
  let busy = false
  const members = $state({})   // bands per music world (from /api/welt, with photos)
  const asked = new Set()

  // new step → scroll to the top
  $effect(() => {
    step
    untrack(() => window.scrollTo({ top: 0, behavior: smooth() }))
  })

  if (!S.library) loadLibrary().catch(() => {})

  const remember = () => {
    try { localStorage.setItem(`tuttiphon-welcome:${(me.user || '').toLowerCase()}`, 'done') } catch { /* does not matter */ }
    if (S.me) S.me.welcomeSeen = true
    api('/api/seen', { body: { what: 'welcome' } }).catch(() => { /* then only on this device */ })
  }

  /* 2 – music worlds */
  const info = $derived(S.library?.weltInfo || {})
  function toggleWelt(id) {
    p.likes.welten = p.likes.welten.includes(id) ? p.likes.welten.filter((x) => x !== id) : [...p.likes.welten, id]
  }

  /* 3 – favorite bands: bands of the chosen music worlds (with photos) */
  $effect(() => {
    if (step !== 3) return
    for (const w of p.likes.welten) {
      if (asked.has(w)) continue
      asked.add(w)
      api(`/api/welt?id=${encodeURIComponent(w)}`)
        .then((d) => (members[w] = d.memberList.map((m) => [m.name, m.songs, m.id])))
        .catch(() => (members[w] = info[w]?.artists || []))
    }
  })
  const bandList = $derived.by(() => {
    const per = Math.max(8, Math.floor(36 / Math.max(1, p.likes.welten.length)))
    const fromWelten = p.likes.welten.flatMap((w) => (members[w] || info[w]?.artists || []).slice(0, per))
    const heardBands = (heard?.artists || []).slice(0, 12).map((a) => [a.name, 0, a.id])   // most played first
    return [...heardBands, ...(fromWelten.length ? fromWelten : (S.library?.artists || []).slice(0, 30))]
      .filter((x, i, arr) => arr.findIndex((y) => y[0] === x[0]) === i).slice(0, 36)
  })

  /* From listening: preselect favorite worlds and bands when nothing is chosen yet */
  let heard = $state.raw(null)
  api('/api/taste?me=1').then((taste) => {
    if (!taste?.enough) return
    heard = taste
    if (!p.likes.welten.length) p.likes.welten = taste.welten.filter((w) => w.share >= 0.08).map((w) => w.id)
    if (!p.likes.artists.length) p.likes.artists = taste.artists.slice(0, 5).map((a) => a.name)
  }).catch(() => {})
  // music worlds: what you listen to most comes first
  let order = null   // fixed when step 2 is first shown
  const weltenSorted = $derived.by(() => {
    if (step !== 2 && !order) return S.config.welten
    if (!order) order = (heard ? [...S.config.welten].sort((a, b) =>
      (heard.welten.find((x) => x.id === b.id)?.share || 0) - (heard.welten.find((x) => x.id === a.id)?.share || 0)) : S.config.welten).map((w) => w.id)
    return [...S.config.welten].sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id))
  })
  function toggleBand(name) {
    p.likes.artists = p.likes.artists.includes(name) ? p.likes.artists.filter((x) => x !== name) : [...p.likes.artists, name]
  }

  /* 4 – dislikes */
  const genreSuggestions = $derived((S.library?.genres || []).map(([g, n]) => [g, plural(n, 'song', 'songs')]))

  async function createProfile() {
    if (busy) return
    busy = true
    try {
      if (!p.id) {
        // as the server accepts it: letter or digit first, at most 41 characters
        let id = slug(p.name || me.user || 'ich').replace(/^[^a-z0-9]+/, '').slice(0, 36) || 'ich'   // i18n-ignore: fallback id
        while (findPerson(id) || id === 'neu') id = `${id.slice(0, 36)}-${Math.floor(Math.random() * 900 + 100)}`   // i18n-ignore: "neu" is the route of the new-person assistant
        p.id = id
        p.prefix = `${p.name.trim()} · `
      }
      p.name = p.name.trim()
      const i = S.config.personen.findIndex((x) => x.id === p.id)
      if (i >= 0) S.config.personen[i] = clone(p)
      else S.config.personen.push(clone(p))
      changed()
      await save()
      S.me = await api('/api/me')
      if (S.me.own !== p.id) throw new Error(t('The profile could not be created – please choose a different name.'))
      step = 5
      sugg = null
      let list
      try { list = await api(`/api/suggestions?person=${encodeURIComponent(p.id)}`) } catch { list = [] }
      list.filter((x) => x.playlist && !x.shared).slice(0, 3).forEach((x) => picks.add(x.key))
      sugg = list
    } catch (e) {
      toast(e.message, { error: true })
    } finally {
      busy = false
    }
  }

  /* 5 – first playlists */
  const offers = $derived((sugg || []).filter((x) => x.playlist))
  function togglePick(key) {
    if (picks.has(key)) picks.delete(key)
    else picks.add(key)
  }
  function finish() {
    for (const x of (sugg || []).filter((y) => picks.has(y.key) && y.playlist)) {
      S.config.playlists.push({ ...clone(x.playlist), person: p.id, id: uid(x.name), status: 'aktiv', created: today(), source: 'willkommen' })
    }
    if (picks.size) changed()
    remember()
    step = LAST
  }

  function tour() {
    go('#/')
    setTimeout(() => startTour(true), 900)
  }
</script>

{#if !local}
  <div class="page max-w-[920px] mx-auto">
    <div class="grid gap-1.5 mb-[22px]">
      <div class="h-1.5 rounded-full bg-surface-3 overflow-hidden">
        <i class="block h-full bg-accent rounded-full transition-[width] duration-350 ease-soft" style:width="{(step / LAST) * 100}%"></i>
      </div>
      <span class="tiny muted">{step && step < LAST ? t('Step {n} of {total}', { n: step, total: STEPS.length - 2 }) : ''}</span>
    </div>

    <div class="min-h-[50vh]">
      {#if step === 0}
        <!-- 0 – what Tuttiphon does for you -->
        <div class="wel-intro">
          <div class="wel-hero">
            <div class="eyebrow">{t('Welcome to Tuttiphon')}</div>
            <h1>{me.name ? t('Hello {name}!', { name: me.name }) : t('Hello!')}</h1>
            <p class="lead">{t('Tuttiphon puts together playlists from your music library – matching your taste, and they keep themselves up to date. You then find them in Symfonium as usual.')}</p>
          </div>
          <TipCards items={[
            ['sparkles', t('Made for you'), t('You say what you like to hear – Tuttiphon suggests ready-made playlists.')],
            ['dice', t('Something new every day'), t('Mixes regularly put themselves together anew, with just a few songs per band.')],
            ['smartphone', t('Simply in Symfonium'), t('Your playlists show up in Symfonium just like all the others.')],
          ]} />
          <p class="muted small">{t('This takes about two minutes. You can change everything later under “My profile”.')}</p>
          {#if existing || isAdmin()}
            <button class="link small muted" onclick={() => { remember(); go('#/') }}>{t('Later – look around first')}</button>
          {/if}
        </div>
      {:else if step === 1}
        <!-- 1 – profile -->
        <div class="card pad-lg wel-card">
          <h2>{t('What should your profile be called?')}</h2>
          <div class="flex gap-4 items-center">
            <PersonAvatar {p} size={72} />
            <input class="input text-[1.2rem] flex-1 min-w-0" bind:value={p.name} placeholder={t('e.g. your first name')} />
          </div>
          <Field label={t('Your icon')}><GlyphPicker value={p.icon} onpick={(v) => (p.icon = v)} /></Field>
          <Field label={t('Your color')}>
            <div class="toggles">
              {#each COLORS as c, i (c)}
                <button type="button" class="toggle swatch" class:on={p.color === c} aria-label={t('Color {n}', { n: i + 1 })} style:background={c} onclick={() => (p.color = c)}></button>
              {/each}
            </div>
          </Field>
        </div>
      {:else if step === 2}
        <!-- 2 – music worlds -->
        <div>
          <h2 class="mb-1.5">{t('What do you like to listen to?')}</h2>
          <p class="muted mb-4">{t('Tap everything you like – you can pick several. A music world groups similar bands together.')}</p>
          {#if heard}
            <div class="note mb-4 flex gap-2.5 items-center"><Icon name="sparkles" size={18} class="shrink-0" />
              <span>{t('What you listen to most in Symfonium is already selected. Tap whatever does not fit or is missing.')}</span></div>
          {/if}
          <div class="pick g-cards">
            {#each weltenSorted as w (w.id)}
              <button class="pickcard" class:on={p.likes.welten.includes(w.id)} onclick={() => toggleWelt(w.id)}>
                <span class="ck"><Icon name="check" size={14} /></span>
                <Collage artists={info[w.id]?.artists || []} icon={w.icon} title={w.name} />
                <div class="pbody"><span class="muted small ell">{(info[w.id]?.artists || []).slice(0, 3).map((a) => a[0]).join(', ')}</span></div>
              </button>
            {/each}
          </div>
        </div>
      {:else if step === 3}
        <!-- 3 – favorite bands -->
        <div>
          <h2 class="mb-1.5">{t('Your favorite bands')}</h2>
          <p class="muted mb-4">{t('Tap the bands you especially like – they show up more often in your playlists. Not here? Search below.')}</p>
          {#if heard}
            <div class="note mb-4 flex gap-2.5 items-center"><Icon name="sparkles" size={18} class="shrink-0" />
              <span>{t('The bands you listen to most come first. Your five favorites are already selected.')}</span></div>
          {/if}
          <div class="agrid">
            {#each bandList as [name, , id] (name)}
              {@const on = p.likes.artists.includes(name)}
              <button class="acard" class:on onclick={() => toggleBand(name)}>
                <Avatar {name} {id} size={72} />
                <div class="nm">{name}</div>
                {#if on}<span class="acheck"><Icon name="check" size={14} /></span>{/if}
              </button>
            {/each}
          </div>
          <Field label={t('Your selection – you can also search for more bands here')} class="mt-[18px]">
            <ArtistChips items={p.likes.artists} onchange={noop} placeholder={t('Band name …')} />
          </Field>
        </div>
      {:else if step === 4}
        <!-- 4 – dislikes -->
        <div class="card pad-lg wel-card">
          <h2>{t('What do you never want to hear?')}</h2>
          <p class="muted">{t('Completely optional. Bands or genres listed here never show up in your playlists.')}</p>
          <Field label={t('Bands')}><ArtistChips items={p.dislikes.artists} onchange={noop} placeholder={t('Band name …')} /></Field>
          <Field label={t('Genres')}><ChipEditor items={p.dislikes.genres} suggestions={genreSuggestions} onchange={noop} placeholder={t('e.g. Schlager')} /></Field>
        </div>
      {:else if step === 5}
        <!-- 5 – first playlists -->
        {#if !sugg}
          <div class="empty">
            <div class="big"><Icon name="sparkles" size={40} /></div>
            <b>{t('Looking for playlists that suit you …')}</b>
          </div>
        {:else if !offers.length}
          <div class="empty">
            <b>{t('No suggestions right now')}</b>
            <div>{t('More favorite worlds bring more ideas – you can also create playlists yourself.')}</div>
          </div>
        {:else}
          <div>
            <h2 class="mb-1.5">{t('Your first playlists')}</h2>
            <p class="muted mb-1.5">{t('I have already selected a few suggestions – tap what you would like to have.')}</p>
            <p class="hint mb-4">{t('“Mix” means: it regularly puts itself together anew and stays the same in between – ideal for downloading in Symfonium. Navidrome reshuffles the others every time they are played.')}</p>
            <div class="pick g-cards">
              {#each offers as x (x.key)}
                <button class="pickcard" class:on={picks.has(x.key)} onclick={() => togglePick(x.key)}>
                  <span class="ck"><Icon name="check" size={14} /></span>
                  <div class="grid grid-cols-[72px_minmax(0,1fr)] gap-3 p-3 items-center">
                    <Mosaic covers={x.covers} marks={plEmoji(x.playlist)} />
                    <div class="min-w-0">
                      <b>{x.title}</b>
                      <div class="muted small">{x.why}</div>
                      <div class="tiny muted">{x.playlist.type === 'mix' ? t('Mix') : plural(x.count, 'song', 'songs')}</div>
                    </div>
                  </div>
                </button>
              {/each}
            </div>
          </div>
        {/if}
      {:else}
        <!-- 6 – done -->
        <div class="wel-intro">
          <div class="wel-hero">
            <div class="hi size-14 rounded-[18px] bg-[rgba(34,197,94,.15)] text-ok"><Icon name="check" size={28} /></div>
            <h1>{t('Done – great to have you here!')}</h1>
            <p class="lead">
              {picks.size
                ? tn(picks.size, 'Your playlist will be in Navidrome in a moment. In Symfonium it appears under “Playlists” after the next sync.',
                  'Your {n} playlists will be in Navidrome in a moment. In Symfonium they appear under “Playlists” after the next sync.')
                : t('Under “Discover” you always find ready-made suggestions for you.')}
            </p>
          </div>
          <TipCards items={[
            ['home', t('For you'), t('Your mixes of today and new suggestions – your home page.')],
            ['user', t('My profile'), t('Change favorite bands and dislikes at any time.')],
            ['help', t('Help'), t('Questions? The question mark next to every heading explains the page.')],
          ]} />
          <div class="btns justify-center">
            <button class="btn primary lg" onclick={tour}><Icon name="compass" size={18} />{t('Short tour')}</button>
            <a class="btn lg" href="#/">{t('Get started right away')}</a>
          </div>
        </div>
      {/if}
    </div>

    <div class="wiz-foot">
      {#if step > 0 && step < LAST}
        <button class="btn" onclick={() => step--}><Icon name="left" size={16} />{t('Back')}</button>
      {:else}
        <span></span>
      {/if}
      {#if step === 0}
        <button class="btn primary lg" onclick={() => (step = 1)}>{t('Let’s go')}<Icon name="right" size={16} /></button>
      {:else if step === 4}
        <button class="btn primary max-mobile:whitespace-normal" onclick={createProfile}>{t('Save profile & show suggestions')}<Icon name="right" size={16} /></button>
      {:else if step === 5}
        <button class="btn primary lg" onclick={finish}>
          <Icon name="check" size={18} />{picks.size ? tn(picks.size, 'Create {n} playlist', 'Create {n} playlists') : t('Continue without playlists')}
        </button>
      {:else if step === LAST}
        <span></span>
      {:else}
        <button class="btn primary" disabled={step === 1 && !p.name.trim()} onclick={() => step++}>
          {step === 3 && !p.likes.artists.length ? t('Skip') : t('Next')}<Icon name="right" size={16} />
        </button>
      {/if}
    </div>
  </div>
{/if}

<style>
  .wel-intro { display: grid; gap: 22px; text-align: center; justify-items: center; padding-top: 12px; }
  .wel-hero { display: grid; gap: 10px; justify-items: center; max-width: 640px; }
  .wel-hero h1 { font-size: clamp(1.8rem, 4vw, 2.6rem); }
  /* minmax(0, 1fr): otherwise the name field makes the card wider than the screen on phones */
  .wel-card { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; max-width: 640px; margin: 0 auto; }
</style>
