<!--
  "New playlist" assistant: for whom → music world → vibe → finishing touches & preview.
  query: values from the address (#/neu?person=…&welt=a,b&stil=…&type=mix&every=week&step=…), from the search also
  mood=ruhig,…, instr=piano,… and theme=film,… (a mix by sound: moods, instruments and themes of the AI – next to a
  sound vibe's own ranges) and name=… (suggested name).
  Phone: the music worlds as compact cards in two columns.
-->
<script>
  import { loadMyTaste, byRelevance } from '../lib/taste.svelte.js'
  import { untrack } from 'svelte'
  import Icon from '../components/Icon.svelte'
  import Glyph from '../components/Glyph.svelte'
  import PageHead from '../components/PageHead.svelte'
  import Collage from '../components/Collage.svelte'
  import PersonAvatar from '../components/PersonAvatar.svelte'
  import StepFinish from './wizard/StepFinish.svelte'
  import { showChosen } from '../components/Seg.svelte'
  import { S, findPerson, findWelt, findStil, defaultPerson, weltIds, soundOf, ownPersons, isAdmin, snapshot, changed, MOODS } from '../lib/state.svelte.js'
  import { toast } from '../lib/overlay.svelte.js'
  import { go } from '../lib/router.svelte.js'
  import { api } from '../lib/api.js'
  import { fmt, uid, today, plural } from '../lib/format.js'
  import { GROUP_LABEL } from '../lib/richtungen.js'
  import { loadCatalog, narrowsLibrary } from '../lib/sound.svelte.js'
  import { t, tn } from '../lib/i18n.svelte.js'
  import { smooth } from '../lib/motion.js'

  let { query = '' } = $props()

  const GROUPS = ['Genre', 'Thema', 'Jahreszeit', 'Zeitreise', 'Spezial']   // i18n-ignore: group names are data
  const STEPS = $derived([t('For whom?'), t('Music world'), t('Vibe'), t('Finishing touches')])
  const TG = 'inline-flex align-[-3px] mr-1.5'   // icon in front of a vibe's name
  const admin = isAdmin()
  const persons = ownPersons()
  const single = persons.length <= 1   // only one own profile -> skip "For whom?"
  const first = single ? 1 : 0

  /** Before the finishing touches: sound vibes exist only as a mix; artist lists for editing. */
  function prepareFinish(x) {
    if (soundOf(x) && x.type !== 'mix') { x.type = 'mix'; x.mix ??= { size: 40, perArtist: 3, every: 'week' } }
    x.addArtists ??= []
    x.excludeArtists ??= []
  }

  // check values from the address (bookmarks/old links can point to deleted things)
  const start = untrack(() => {
    const params = new URLSearchParams(query)
    const welt = params.get('welt')
    const x = { person: params.get('person') || defaultPerson(), welt: welt ? (welt.includes(',') ? welt.split(',') : welt) : [], stil: params.get('stil') || '*', id: uid('playlist') }
    const every = ['day', 'week', 'month'].includes(params.get('every')) ? params.get('every') : null   // i18n-ignore: stored values
    if (params.get('type') === 'mix') {
      x.type = 'mix'
      if (every) x.mix = { size: 40, perArtist: 3, every }
    }
    if (!persons.some((p) => p.id === x.person)) x.person = defaultPerson()
    const okWelten = weltIds(x).filter((w) => findWelt(w))
    x.welt = okWelten.length === 1 ? okWelten[0] : okWelten
    if (x.stil !== '*' && !findStil(x.stil)) x.stil = '*'
    const moods = (params.get('mood') || '').split(',').filter((m) => m in MOODS)
    // instrument and theme ids of the AI – checked against the catalog below, as soon as it is loaded
    const idList = (key) => [...new Set((params.get(key) || '').split(',').filter((x) => /^[a-z]{2,32}$/.test(x)))].slice(0, 12)
    const instr = idList('instr'), themes = idList('theme')
    if (moods.length || instr.length || themes.length) {   // e.g. "calm children's songs" from the search: only Tuttiphon picks by sound -> a mix
      // the playlist's own filter replaces that of its vibe: a sound vibe ("In the background") keeps its ranges
      x.sound = x.stil !== '*' ? $state.snapshot(findStil(x.stil)?.sound) || {} : {}
      if (moods.length) x.sound.moods = moods
      if (instr.length) x.sound.instruments = instr   // an instrument or theme narrows enough for “All × Everything”
      if (themes.length) x.sound.themes = themes
      x.type = 'mix'
      x.mix = { size: 40, perArtist: 3, every: every || 'week' }
    }
    const name = (params.get('name') || '').trim().slice(0, 120)
    if (name) x.name = name
    let step = Math.max(first, Math.min(3, Number(params.get('step')) || 0))
    if (step >= 3 && !(weltIds(x).length || x.stil !== '*' || narrowsLibrary(x.sound))) step = 1   // e.g. an old link to a deleted music world -> choose first
    if (step === 3) prepareFinish(x)
    return { x, step }
  })

  let d = $state(start.x)
  let step = $state(start.step)
  let counts = $state.raw(null)   // songs per vibe for the chosen music world + person

  const ids = $derived(weltIds(d))
  const valid = $derived(ids.length > 0 || (!!d.stil && d.stil !== '*') || narrowsLibrary(d.sound))

  // instruments and themes from the address: only those the AI knows
  if (start.x.sound?.instruments || start.x.sound?.themes) {
    loadCatalog().then((c) => {
      for (const [key, known] of [['instruments', c.items], ['themes', c.themes]]) {
        const have = d.sound?.[key]
        if (!have || !known) continue
        const ok = have.filter((x) => known.some((i) => i.id === x))
        if (ok.length === have.length) continue
        if (ok.length) d.sound[key] = ok
        else delete d.sound[key]
      }
      if (d.sound && !Object.keys(d.sound).length) delete d.sound
    }).catch(() => {})
  }

  function show(i) {
    if (i === 3) prepareFinish(d)
    step = i
  }
  $effect(() => {
    void step
    untrack(() => window.scrollTo({ top: 0, behavior: smooth() }))
  })

  // step "vibe": fetch song counts – only take them if the selection is still the same
  $effect(() => {
    if (step !== 2 || counts) return
    untrack(() => {
      const body = { welt: $state.snapshot(d.welt), person: d.person }
      const key = JSON.stringify([body.welt, body.person])
      api('/api/counts', { body }).then((c) => {
        if (key === JSON.stringify([$state.snapshot(d.welt), d.person])) counts = c
      }).catch(() => {})
    })
  })

  // music world
  const info = $derived(S.library?.weltInfo || {})
  const liked = $derived(new Set(findPerson(d.person)?.likes?.welten || []))
  loadMyTaste()
  const sorted = $derived(byRelevance(S.config.welten, liked))
  function toggleWelt(id) {
    const next = ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]
    d.welt = next.length === 1 ? next[0] : next
    counts = null
  }

  // vibe
  const stilGroups = $derived([...new Set([...GROUPS, ...S.config.stile.map((s) => s.group || 'Sonstiges')])]   // i18n-ignore: group name
    .map((g) => [g, S.config.stile.filter((s) => (s.group || 'Sonstiges') === g)]).filter(([, st]) => st.length))   // i18n-ignore: group name
  const separate = $derived(S.config.welten.filter((w) => w.separate).map((w) => w.name))

  let created = false
  function create() {
    if (created || !valid) return   // double click
    if (d.stil !== '*' && !findStil(d.stil)) { toast(t('This vibe no longer exists – please choose another one.'), { error: true }); show(2); return }
    created = true
    snapshot()
    const p = { ...$state.snapshot(d), status: 'aktiv', created: today(), source: 'assistent' }
    if (Array.isArray(p.welt) && !p.welt.length) p.welt = '*'
    for (const k of ['addArtists', 'excludeArtists']) if (!p[k]?.length) delete p[k]
    if (p.type === 'mix') { delete p.sort; delete p.limit; delete p.notPlayedDays } else delete p.mix
    S.config.playlists.push(p)
    changed()
    toast(S.config.settings.autoApply !== false ? t('Playlist created – will be in Navidrome shortly') : t('Playlist created'), { undo: true })
    go(`#/playlist/${encodeURIComponent(p.id)}`)
  }
</script>

{#snippet check()}<span class="ck"><Icon name="check" size={16} /></span>{/snippet}

{#snippet opt(id, label, n, icon = undefined)}
  <button class="toggle" class:on={d.stil === id} disabled={n === 0} onclick={() => (d.stil = id)}>
    {#if icon !== undefined}<Glyph value={icon} size={15} class={TG} />{/if}{label}
    {#if n != null}<span class="n">{fmt(n)}</span>{/if}
  </button>
{/snippet}

<div class="page max-w-[1100px]">
  <PageHead title={t('New playlist')} eyebrow={t('Assistant')}
    sub={single ? t('In three short steps – you always see which songs you get.') : t('In four short steps – you always see which songs you get.')} />

  <div class="stepper" {@attach showChosen(step)}>
    {#each STEPS as label, i (i)}
      {#if i >= first}
        <button class:on={i === step} class:done={i < step} onclick={() => { if (i <= 2 || valid) show(i) }}>
          <span class="n">{i < step ? '✓' : i + 1 - first}</span>{label}
        </button>
      {/if}
    {/each}
  </div>

  <div>
    {#if step === 0}
      <div class="pick g-cards grid-cols-[repeat(auto-fill,minmax(200px,1fr))]">
        {#each persons as p (p.id)}
          <button class="pickcard person" class:on={d.person === p.id} onclick={() => { d.person = p.id; counts = null; show(1) }}>
            {@render check()}
            <PersonAvatar {p} size={72} />
            <h3>{p.name}</h3>
            <div class="muted small">{p.public ? t('visible to everyone') : admin ? t('private for {user}', { user: p.user }) : t('only for you')}</div>
            {#if p.likes?.welten?.length}
              <div class="tiny muted">{t('likes {list}', { list: p.likes.welten.map((w) => findWelt(w)?.name).filter(Boolean).join(', ') })}</div>
            {/if}
          </button>
        {/each}
      </div>
    {:else if step === 1}
      <p class="muted mb-4">{t('Who should play? Choose one or more music worlds – or “All” for the whole library.')}</p>
      <div class="pick g-cards worlds max-mobile:grid-cols-2 max-mobile:gap-2.5">
        <button class="pickcard" class:on={!ids.length} onclick={() => { d.welt = []; counts = null }}>
          {@render check()}
          <div class="collage" style:background={'var(--grad)'}>
            <div class="on-top"><span class="ico"><Glyph value="globe" size={28} /></span><h3>{t('All')}</h3></div>
          </div>
          <div class="pbody">
            <b>{t('The whole library')}</b>
            <span class="muted small">{separate.length ? tn(separate.length, 'without the world “{list}”', 'without the worlds “{list}”', { list: separate.join(', ') }) : t('without separate worlds')}</span>
          </div>
        </button>
        {#each sorted as w (w.id)}
          {@const wi = info[w.id]}
          <button class="pickcard" class:on={ids.includes(w.id)} onclick={() => toggleWelt(w.id)}>
            {@render check()}
            <Collage artists={wi?.artists || []} icon={w.icon} title={w.name} />
            <div class="pbody">
              <b class="hidden max-mobile:block leading-tight">{w.name}</b>
              <b class="max-mobile:hidden">{plural(wi?.members || 0, 'band', 'bands')} · {plural(wi?.songs || 0, 'song', 'songs')}</b>
              <span class="hidden max-mobile:block muted small">{plural(wi?.songs || 0, 'song', 'songs')}</span>
              <span class="muted small ell max-mobile:hidden">{(wi?.artists || []).slice(0, 3).map((a) => a[0]).join(', ')}</span>
              {#if liked.has(w.id)}<span class="pill acc justify-self-start">♥ {t('Favorite world')}</span>{/if}
            </div>
          </button>
        {/each}
      </div>
    {:else if step === 2}
      {@const c = counts || {}}
      <p class="muted mb-4">{t('What should play? The numbers show how many songs match each one.')}</p>
      <div class="grid gap-[22px]">
        {#if ids.length}<div class="toggles">{@render opt('*', t('Everything from the music world'), c['*'])}</div>{/if}
        {#each stilGroups as [g, st] (g)}
          <div class="field">
            <span class="lbl">{GROUP_LABEL[g] ?? g}</span>
            <div class="toggles">{#each st as s (s.id)}{@render opt(s.id, s.name, c[s.id], s.icon)}{/each}</div>
          </div>
        {/each}
      </div>
    {:else}
      <StepFinish {d} />
    {/if}
  </div>

  <div class="wiz-foot">
    {#if step > first}
      <button class="btn" onclick={() => show(step - 1)}><Icon name="left" size={16} />{t('Back')}</button>
    {:else}
      <a class="btn ghost" href="#/playlists">{t('Cancel')}</a>
    {/if}
    {#if step < 3}
      <button class="btn primary" disabled={step === 2 && !valid} onclick={() => show(step + 1)}>{t('Next')}<Icon name="right" size={16} /></button>
    {:else}
      <button class="btn primary lg" disabled={!valid} onclick={create}><Icon name="check" size={18} />{t('Create playlist')}</button>
    {/if}
  </div>
</div>

<style>
  /* phone: two compact columns – small picture with the icon, name and song count below it */
  @media (max-width: 900px) {
    .worlds :global(.collage) { aspect-ratio: 3 / 1.4; }
    .worlds :global(.collage .on-top) { left: 8px; bottom: 8px; }
    .worlds :global(.collage .on-top .ico) { width: 32px; height: 32px; border-radius: 10px; }
    .worlds :global(.collage .on-top .ico svg) { width: 18px; height: 18px; }
    .worlds :global(.collage .on-top h3) { display: none; }
    .worlds .pbody { padding: 8px 10px 10px; gap: 2px; }
    .worlds .ck { top: 6px; right: 6px; width: 22px; height: 22px; }
  }
</style>
