<!--
  "New person" assistant (administrators): Who? → Navidrome account (one without a person) → favorite worlds → vibes →
  matching playlists. The person only enters S.config at the fourth step; before that everything lives only here in the
  assistant. From People → “Add person” of a merged profile (settings.mergedPersons) it starts with its name and drops
  the entry once the person is created.
-->
<script>
  import { SvelteSet } from 'svelte/reactivity'
  import Icon from '../../components/Icon.svelte'
  import Empty from '../../components/Empty.svelte'
  import Field from '../../components/Field.svelte'
  import Mosaic from '../../components/Mosaic.svelte'
  import Select from '../../components/Select.svelte'
  import Loading from '../../components/Loading.svelte'
  import PageHead from '../../components/PageHead.svelte'
  import ChipEditor from '../../components/ChipEditor.svelte'
  import ArtistChips from '../../components/ArtistChips.svelte'
  import GlyphPicker from '../../components/GlyphPicker.svelte'
  import PersonAvatar from '../../components/PersonAvatar.svelte'
  import LikedWelten from './LikedWelten.svelte'
  import StilToggles from './StilToggles.svelte'
  import ColorPick from './ColorPick.svelte'
  import { showChosen } from '../../components/Seg.svelte'
  import { S, findPerson, changed, save, loadStatus, passKey } from '../../lib/state.svelte.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { go } from '../../lib/router.svelte.js'
  import { api } from '../../lib/api.js'
  import { slug, uid, today, clone } from '../../lib/format.js'
  import { plEmoji } from '../../lib/playlist.js'
  import { genreSuggestions } from '../../lib/richtungen.js'
  import { COLORS, users, pwOk, takenAccounts, takeDraft } from './shared.js'
  import { t, tn } from '../../lib/i18n.svelte.js'

  const STEPS = $derived([t('Who?'), 'Navidrome', t('Favorite worlds'), t('Vibes'), t('Playlists')])
  const noop = () => {}

  /** Navidrome accounts without a person (null = still loading) – the family's has one */
  let us = $state.raw(null)
  const draft = takeDraft()   // a merged profile from People (settings.mergedPersons)
  const p = $state({ id: '', name: draft?.name || '', icon: 'i:music', color: COLORS[Math.floor(Math.random() * COLORS.length)], user: '',
    prefix: '', likes: { welten: [], stile: [], artists: [] }, dislikes: { artists: [], genres: [] },
    ...(draft?.child ? { child: true, clean: true } : {}) })
  let step = $state(0)
  let pw = $state('')
  let pwState = $state(null)
  const picks = new SvelteSet()
  let sugg = $state.raw(null)

  let usersError = $state('')
  users().then((all) => {
    const taken = takenAccounts()
    const list = all.filter((u) => !taken.has(u.name.toLowerCase()))
    p.user = list.find((u) => !u.admin)?.name || list[0]?.name || ''
    us = list
    usersError = users.error
  })

  const canNext = $derived(step === 0 ? !!p.name.trim() : step === 1 ? !!p.user : true)
  const mineList = $derived((sugg || []).filter((s) => s.person === p.id && s.playlist))

  async function testPw() {
    const r = await api('/api/env/test', { body: { user: p.user, password: pw } }).catch((e) => ({ ok: false, error: e.message }))
    pwState = r.ok ? 'ok' : r.error
  }

  let busy = false
  async function createPerson() {
    if (busy) return   // double click
    busy = true
    try {
      if (!p.id) {   // create the first time – after "Back" only update
        let id = slug(p.name || 'person')
        while (findPerson(id) || id === 'neu') id += '-2'   // i18n-ignore: "neu" is the route of this assistant
        p.id = id
      }
      p.prefix ||= `${p.name} · `
      if (pw) {   // only save a password that actually works
        const r = await api('/api/env/test', { body: { user: p.user, password: pw } }).catch((e) => ({ ok: false, error: e.message }))
        if (r.ok) await api('/api/env', { method: 'PUT', body: { [passKey(p.user)]: pw } }).catch(() => {})
        else toast(t('The password for “{user}” does not work and was not saved – enter it later in Settings.', { user: p.user }), { error: true })
      }
      const i = S.config.personen.findIndex((x) => x.id === p.id)
      if (i >= 0) S.config.personen[i] = clone(p)
      else S.config.personen.push(clone(p))
      if (draft) {   // the merged profile has its own person now
        const rest = (S.config.settings.mergedPersons || []).filter((x) => x?.name !== draft.name)
        if (rest.length) S.config.settings.mergedPersons = rest
        else delete S.config.settings.mergedPersons
      }
      changed()
      await save()
      loadStatus()
    } finally {
      busy = false
    }
    step = 4
    sugg = null
    let list
    try { list = await api(`/api/suggestions?person=${encodeURIComponent(p.id)}`) } catch { list = [] }
    list.filter((s) => s.person === p.id && s.playlist && !s.shared).slice(0, 3).forEach((s) => picks.add(s.key))
    sugg = list
  }

  let finished = false
  function finish() {
    if (finished) return
    finished = true
    for (const s of (sugg || []).filter((x) => picks.has(x.key) && x.playlist)) {
      S.config.playlists.push({ ...clone(s.playlist), id: uid(s.name), status: 'aktiv', created: today(), source: 'assistent' })
    }
    changed()
    toast(picks.size
      ? tn(picks.size, '{name} is on board – {n} playlist will be in Navidrome shortly', '{name} is on board – {n} playlists will be in Navidrome shortly', { name: p.name })
      : t('{name} is on board', { name: p.name }))
    go(`#/person/${p.id}`)
  }
</script>

<div class="page max-w-[1100px]">
  <PageHead title={t('New person')} sub={t('A few questions – then you get matching playlists right away.')} eyebrow={t('Assistant')} />

  {#if !us}
    <Loading />
  {:else}
    <div class="stepper" {@attach showChosen(step)}>
      {#each STEPS as label, i (label)}
        <button class:on={i === step} class:done={i < step} onclick={() => { if (i < step) step = i }}>
          <span class="n">{i < step ? '✓' : i + 1}</span>{label}
        </button>
      {/each}
    </div>

    <div>
      {#if step === 0}
        <div class="card pad-lg grid gap-5 max-w-[640px]">
          <div class="flex gap-[18px] items-center">
            <PersonAvatar {p} size={84} />
            <label class="f flex-1">{t('What is the person’s name?')}
              <input class="input text-[1.2rem]" bind:value={p.name} placeholder={t('e.g. Mia')} />
            </label>
          </div>
          <Field label={t('Icon')}><GlyphPicker value={p.icon} onpick={(v) => (p.icon = v)} /></Field>
          <Field label={t('Color')}><ColorPick value={p.color} size={36} onpick={(c) => (p.color = c)} /></Field>
        </div>
      {:else if step === 1}
        <div class="card pad-lg grid gap-[18px] max-w-[640px]">
          <p class="muted">{p.name
            ? t('Which Navidrome account does {name} use? The playlists end up there, and the stars & favorites of this account count.', { name: p.name })
            : t('Which Navidrome account does the person use? The playlists end up there, and the stars & favorites of this account count.')}</p>
          {#if us.length}
            <label class="f">{t('Navidrome user')}
              <Select options={us.map((u) => [u.name, u.name + (u.admin ? ' · Admin' : '')])} value={p.user} onchange={(v) => { p.user = v; pwState = null }} />
            </label>
          {:else if usersError}
            <div class="err-t small">{t('Could not load the accounts from Navidrome: {error}', { error: usersError })}</div>
          {:else}
            <div class="note">{t('Every Navidrome account already has a person.')}</div>
          {/if}
          <div class="hint">{t('User missing? You create new accounts in Navidrome under Settings → Users, then reload here.')}{#if S.status?.env?.webUrl}{' '}<a href="{S.status.env.webUrl}/app/#/user" target="_blank" rel="noopener">{t('Open Navidrome ↗')}</a>{/if}</div>
          {#if !p.user}
            <!-- no account to choose -->
          {:else if pwOk(p.user)}
            <div class="note">{t('✓ A password is already stored for this account.')}</div>
          {:else}
            <div class="field">
              <span class="lbl">{t('Password for “{user}” – optional, for stars & an exact preview', { user: p.user })}</span>
              <div class="btns">
                <input class="input flex-1" type="password" autocomplete="new-password" bind:value={pw} aria-label={t('Password')} />
                <button class="btn" onclick={testPw}>{t('Test')}</button>
              </div>
              {#if pwState}<div class="small {pwState === 'ok' ? 'ok-t' : 'err-t'}">{pwState === 'ok' ? t('✓ works') : `✕ ${pwState}`}</div>{/if}
            </div>
          {/if}
          <label class="f">{t('Name prefix')}
            <input class="input" value={p.prefix || `${p.name} · `} onchange={(e) => (p.prefix = e.currentTarget.value)} />
          </label>
        </div>
      {:else if step === 2}
        <div>
          <p class="muted mb-4">{t('What does {name} like to listen to? You can pick several.', { name: p.name })}</p>
          <LikedWelten {p} />
        </div>
      {:else if step === 3}
        <div class="card pad-lg grid gap-[18px]">
          <p class="muted">{t('Optional: favorite vibes – and what is off limits.')}</p>
          <Field label={t('Likes')}><StilToggles {p} /></Field>
          <Field label={t('Dislikes – bands')}><ArtistChips items={p.dislikes.artists} onchange={noop} /></Field>
          <Field label={t('Dislikes – genres')}><ChipEditor items={p.dislikes.genres} suggestions={genreSuggestions()} onchange={noop} placeholder={t('e.g. Schlager')} /></Field>
        </div>
      {:else if !sugg}
        <Loading text={t('Looking for matching playlists …')} />
      {:else if !mineList.length}
        <Empty icon={p.icon} title={t('No suggestions right now')} text={t('More favorite worlds bring more ideas – or create a playlist yourself.')} />
      {:else}
        <div>
          <p class="muted mb-4">{t('Matching playlists for {name} – tap to select.', { name: p.name })}</p>
          <div class="pick g-cards">
            {#each mineList as s (s.key)}
              <button class="pickcard" class:on={picks.has(s.key)} aria-pressed={picks.has(s.key)}
                onclick={() => { if (picks.has(s.key)) picks.delete(s.key); else picks.add(s.key) }}>
                <span class="ck"><Icon name="check" size={14} /></span>
                <div class="grid grid-cols-[72px_minmax(0,1fr)] gap-3 p-3 items-center">
                  <Mosaic covers={s.covers} marks={plEmoji(s.playlist)} />
                  <div class="min-w-0">
                    <b>{s.title}</b>
                    <div class="muted small">{s.why}</div>
                    {#if s.shared}<span class="pill mt-1.5">{t('already exists for everyone')}</span>{/if}
                  </div>
                </div>
              </button>
            {/each}
          </div>
        </div>
      {/if}
    </div>

    <div class="wiz-foot">
      {#if step}
        <button class="btn" onclick={() => step--}><Icon name="left" size={16} />{t('Back')}</button>
      {:else}
        <a class="btn ghost" href="#/personen">{t('Cancel')}</a>
      {/if}
      {#if step < 3}
        <button class="btn primary" disabled={!canNext} onclick={() => step++}>{t('Next')}<Icon name="right" size={16} /></button>
      {:else if step === 3}
        <button class="btn primary" onclick={createPerson}>{t('Create person & show suggestions')}<Icon name="right" size={16} /></button>
      {:else}
        <button class="btn primary lg" onclick={finish}><Icon name="check" size={18} />{picks.size ? tn(picks.size, 'Create {n} playlist & finish', 'Create {n} playlists & finish') : t('Done')}</button>
      {/if}
    </div>
  {/if}
</div>
