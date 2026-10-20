<!--
  A person's profile: header, taste from listening, preferences, "dislikes", kid-safe mode, notifications,
  profile (prefix, account/visibility), appearance (name, icon, color – folded) and their playlists. p: person from S.config (changed directly) · self: a user looking at their own profile.
-->
<script>
  import PushDevice from '../../components/PushDevice.svelte'
  import HelpLink from '../../components/HelpLink.svelte'
  import { untrack } from 'svelte'
  import Icon from '../../components/Icon.svelte'
  import Glyph from '../../components/Glyph.svelte'
  import Empty from '../../components/Empty.svelte'
  import Field from '../../components/Field.svelte'
  import Section from '../../components/Section.svelte'
  import Seg from '../../components/Seg.svelte'
  import Select from '../../components/Select.svelte'
  import ChipEditor from '../../components/ChipEditor.svelte'
  import ArtistChips from '../../components/ArtistChips.svelte'
  import GlyphPicker from '../../components/GlyphPicker.svelte'
  import PersonAvatar from '../../components/PersonAvatar.svelte'
  import PlaylistCard from '../../components/PlaylistCard.svelte'
  import TasteCard from '../../components/TasteCard.svelte'
  import LikedWelten from './LikedWelten.svelte'
  import TasteExclude from './TasteExclude.svelte'
  import StilToggles from './StilToggles.svelte'
  import ColorPick from './ColorPick.svelte'
  import { S, findPerson, defaultPerson, changed, snapshot, isAdmin } from '../../lib/state.svelte.js'
  import { confirmDialog, toast } from '../../lib/overlay.svelte.js'
  import { go } from '../../lib/router.svelte.js'
  import { passwordModal } from '../../lib/account.js'
  import { genreSuggestions } from '../../lib/richtungen.js'
  import { users, pwOk } from './shared.js'
  import Switch from '../../components/Switch.svelte'
  import { api } from '../../lib/api.js'
  import { t, tn } from '../../lib/i18n.svelte.js'

  let { p, self = false } = $props()

  // create missing fields (separate statements – see the proxy trap in frontend/README.md)
  untrack(() => {
    p.likes ??= { welten: [], stile: [], artists: [] }
    p.dislikes ??= { artists: [], genres: [] }
  })

  const ch = () => changed()
  let us = $state.raw([])
  untrack(() => { if (!self) users().then((list) => (us = list)) })

  const userOptions = $derived([...new Set([...us.map((u) => u.name), p.user].filter(Boolean))].map((u) => [u, u]))
  const mine = $derived(S.config.playlists.filter((x) => (x.person || defaultPerson()) === p.id && x.status !== 'papierkorb'))

  // kid-safe mode: anyone may turn it on, only the administrator may turn it off (otherwise the server keeps it on)
  const cleanLocked = untrack(() => !isAdmin() && !!p.clean)
  // suggestion for a topic that is hard to guess
  const suffix = Math.random().toString(36).slice(2, 7)
  let topic = $state(untrack(() => p.push || ''))
  const topicOk = $derived(/^[A-Za-z0-9_-]{1,64}$/.test(topic))
  function setTopic(e) {
    const v = e.currentTarget.value.trim()
    if (v && !/^[A-Za-z0-9_-]{1,64}$/.test(v)) {   // otherwise the server would reject the whole save
      toast(t('Please use only letters, digits, - and _ for the topic'), { error: true })
      return
    }
    p.push = v
    ch()
  }
  async function testPush() {
    try {
      const r = await api('/api/notify/test', { body: { person: p.id, topic } })
      toast(r.ok ? t('Test message sent') : r.error, { error: !r.ok })
    } catch (e) { toast(e.message, { error: true }) }
  }

  async function deletePerson() {
    const n = S.config.playlists.filter((x) => x.person === p.id).length
    if (!await confirmDialog(t('Delete {name}?', { name: p.name }),
      n ? tn(n, '{n} playlist goes to “{name}”.', '{n} playlists go to “{name}”.', { name: findPerson(defaultPerson()).name }) : t('This person has no playlists.'),
      t('Delete'), true)) return
    snapshot()
    S.config.playlists.forEach((x) => {
      if (x.person === p.id) x.person = defaultPerson()
      if (Array.isArray(x.together) && x.together.includes(p.id)) {   // family mix: without this person
        x.together = x.together.filter((id) => id !== p.id)
        if (x.together.length < 2) delete x.together
        if (!x.together && !x.fav && !x.review && !x.radio && !(x.mix?.flavor === 'geschmack')
          && (!x.welt || x.welt === '*') && (x.stil || '*') === '*') x.mix = { ...x.mix, flavor: 'geschmack' }
      }
    })
    const name = p.name
    S.config.personen = S.config.personen.filter((x) => x !== p)
    changed()
    toast(t('{name} deleted', { name }), { undo: true })
    go('#/personen')
  }

  const cleanText = $derived(self
    ? (cleanLocked ? t('Detected from the lyrics. Applies to all playlists and mixes of your profile – the administrator can turn it off.')
      : t('Detected from the lyrics. Applies to all playlists and mixes of your profile.'))
    : (cleanLocked ? t('Detected from the lyrics. Applies to all playlists and mixes of {name} – the administrator can turn it off.', { name: p.name })
      : t('Detected from the lyrics. Applies to all playlists and mixes of {name}.', { name: p.name })))
</script>

<div class="page">
  {#if self}
    <a href="#/" class="link inline-flex gap-1.5 items-center mt-2.5 mb-3.5"><Icon name="left" size={16} />{t('For you')}</a>
  {:else}
    <a href="#/personen" class="link inline-flex gap-1.5 items-center mt-2.5 mb-3.5"><Icon name="left" size={16} />{t('All people')}</a>
  {/if}

  <div class="hero grad">
    <div class="hero-row items-center">
      <PersonAvatar {p} size={120} />
      <div class="hero-text">
        <div class="eyebrow">{self ? t('My profile') : t('Person')}</div>
        <h1>{p.name}<HelpLink /></h1>
        {#if self}<p class="muted max-w-[560px]">{t('What you enter here decides your suggestions and what ends up in your playlists. Changes apply right away.')}</p>{/if}
        <div class="hero-meta">
          <span>Navidrome: {p.user}</span>
          <span>{p.public ? t('Playlists visible to everyone') : self ? t('Playlists only for you') : t('Playlists private')}</span>
          {#if self}
            {#if S.me?.passwordStored}
              <span class="pill ok">{t('Statistics on')}</span>
            {:else}
              <a class="pill warn no-underline" href="#/einstellungen/konto"><Icon name="key" size={12} />{t('Turn on statistics')}</a>
            {/if}
          {:else if pwOk(p.user)}
            <span class="pill ok">{t('Password stored')}</span>
          {:else}
            <button class="pill warn border-0 cursor-pointer" onclick={() => passwordModal(p.user)}><Icon name="lock" size={12} />{t('Password missing – enter it')}</button>
          {/if}
        </div>
        <div class="btns mt-2">
          <a class="btn white" href="#/neu?person={p.id}&step=1"><Icon name="plus" size={17} />{self ? t('New playlist') : t('Playlist for {name}', { name: p.name })}</a><!-- i18n-ignore: route -->
          <a class="btn" href="#/entdecken"><Icon name="compass" size={17} />{t('Suggestions')}</a>
        </div>
      </div>
    </div>
  </div>

  {#if p.user}
    <div class="section"><TasteCard person={p.id} likes={p.likes} {self} name={p.name} onchange={ch} /></div>
    {#if p.id !== S.config.settings.defaultPerson}<div class="section"><TasteExclude {p} {self} onchange={ch} /></div>{/if}
  {/if}

  <div class="card section grid gap-4" data-guide="likes">
    <h2 class="ih"><span class="hi"><Icon name="heart" size={18} /></span>{self ? t('What you like to hear') : t('Preferences')}</h2>
    {#if self}<p class="muted small -mt-2">{t('Your suggestions under “Discover” and “For you” are built from this.')}</p>{/if}
    <Field label={self ? t('Favorite music worlds') : t('Likes to hear – music worlds')}><LikedWelten {p} compact onchange={ch} /></Field>
    <Field label={self ? t('Favorite vibes') : t('Likes to hear – vibes')}><StilToggles {p} onchange={ch} /></Field>
    <Field label={self ? t('Favorite bands – show up more often in your mixes') : t('Favorite bands – go into the personal mix')}>
      <ArtistChips items={p.likes.artists} onchange={ch} />
    </Field>
  </div>

  <div class="card section grid gap-4" data-guide="dislikes">
    <h2 class="ih"><span class="hi"><Glyph value="ban" size={18} /></span>{t('Dislikes')}</h2>
    <p class="muted small">{self ? t('Never ends up in your playlists – whatever the music world or vibe.') : t('Never ends up in {name}’s playlists – whatever the music world or vibe.', { name: p.name })}</p>
    <div class="frow">
      <Field label={t('Bands')}><ArtistChips items={p.dislikes.artists} onchange={ch} /></Field>
      <Field label={t('Genre contains')}><ChipEditor items={p.dislikes.genres} suggestions={genreSuggestions()} placeholder={t('e.g. Schlager')} onchange={ch} /></Field>
    </div>
  </div>

  <div class="g-2 section">
    <div class="card grid gap-3 content-start" data-guide="kinderschutz">
      <h2 class="ih"><span class="hi"><Icon name="shield-check" size={18} /></span>{t('Kid-safe mode')}</h2>
      <Switch checked={!!p.clean} disabled={cleanLocked} onchange={(v) => { p.clean = v; ch() }}
        label={t('Leave out songs with explicit lyrics')} />
      <p class="muted small">{cleanText}</p>
    </div>
    {#if S.config.settings.notify?.enabled}
      <div class="card grid gap-3 content-start min-w-0" data-guide="push">
        <h2 class="ih"><span class="hi"><Icon name="bell" size={18} /></span>{t('To your phone')}</h2>
        <p class="muted small">{self
          ? t('You get news from your favorite bands and your monthly recap as a notification – on every device where you turn it on.')
          : t('{name} gets news from their favorite bands and their monthly recap as a notification – on the devices they turn on in their profile.', { name: p.name })}</p>
        {#if self}<PushDevice />{/if}
        <details class="small" open={!!p.push}>
          <summary class="muted cursor-pointer">{self ? t('Or via the ntfy app') : t('Via the ntfy app')}</summary>
          <div class="grid gap-2 mt-2">
            <p class="muted">{t('Subscribe to the topic in the ntfy app, server: {server}.', { server: S.config.settings.notify.server || 'https://ntfy.sh' })}</p>
            <div class="flex gap-2 items-center">
              <input class="input flex-1 min-w-0" value={p.push || ''} placeholder={t('Topic, e.g. {id}-music-{suffix}', { id: p.id, suffix })} aria-label={t('Topic for notifications')}
                oninput={(e) => (topic = e.currentTarget.value.trim())} onchange={setTopic} />
              <button class="btn sm" disabled={!topicOk} onclick={testPush}>{t('Send test')}</button>
            </div>
            <div class="hint">{t('Only letters, digits, - and _. Anyone who knows the topic can read along.')}</div>
          </div>
        </details>
      </div>
    {/if}
  </div>

  <div class="g-2 section">
    <div class="card grid gap-4">
      <h2 class="ih"><span class="hi"><Icon name="user" size={18} /></span>{t('Profile')}</h2>
      <label class="f">{t('Prefix for playlist names')}
        <input class="input" value={p.prefix || ''} placeholder={t('e.g. Mia · ')} onchange={(e) => { p.prefix = e.currentTarget.value; ch() }} />
      </label>
      {#if self}<div class="hint -mt-2">{t('Goes in front of every playlist name – so you spot your playlists in Symfonium at a glance.')}</div>{/if}
      {#if self}
        <div data-guide="sichtbar">
          <Field label={t('Who may see your playlists?')}>
            <Seg options={[['0', t('Only me')], ['1', t('The whole family')]]} value={p.public ? '1' : '0'} onchange={(v) => { p.public = v === '1'; ch() }} />
            <div class="hint">{t('With “family”, everyone sees them in Navidrome and Symfonium – only you can change them.')}</div>
          </Field>
        </div>
      {:else}
        <div class="frow" data-guide="sichtbar">
          <label class="f">{t('Navidrome user')}
            <Select options={userOptions} value={p.user} onchange={(v) => { p.user = v; ch() }} />
          </label>
          <label class="f">{t('Visibility')}
            <Select options={[['1', t('visible to everyone')], ['0', t('private')]]} value={p.public ? '1' : '0'} onchange={(v) => { p.public = v === '1'; ch() }} />
          </label>
        </div>
        {#if p.id === defaultPerson()}
          <div class="hint">{t('Default: new playlists are for this person at first.')}</div>
        {:else}
          <div class="btns">
            <button class="btn sm" onclick={() => { S.config.settings.defaultPerson = p.id; ch() }}>{t('Make default')}</button>
            <button class="btn sm danger" onclick={deletePerson}><Icon name="trash" size={15} />{t('Delete person')}</button>
          </div>
        {/if}
      {/if}
    </div>

    <!-- name, icon and color: rarely changed, so folded -->
    <details class="fold rounded-big">
      <summary class="px-[22px] py-[18px]">
        <h2 class="ih"><span class="hi"><Icon name="palette" size={18} /></span>{t('Appearance')}</h2>
        <span class="muted small font-normal">{t('Name, icon and color')}</span>
      </summary>
      <div class="in px-[22px] pb-[22px]">
        <label class="f">{t('Name')}
          <input class="input" value={p.name} onchange={(e) => { p.name = e.currentTarget.value.trim() || p.name; e.currentTarget.value = p.name; ch() }} />
        </label>
        <Field label={t('Icon')}><GlyphPicker value={p.icon} onpick={(v) => { p.icon = v; ch() }} /></Field>
        <Field label={t('Color')}><ColorPick value={p.color} onpick={(c) => { p.color = c; ch() }} /></Field>
      </div>
    </details>
  </div>

  <Section title={self ? t('Your playlists') : t('{name}’s playlists', { name: p.name })}>
    {#if mine.length}
      <div class="g-pl">{#each mine as x (x.id)}<PlaylistCard p={x} />{/each}</div>
    {:else}
      <Empty icon={p.icon} title={t('No playlists yet')} text={t('Suggestions adapt to the preferences.')}>
        <a class="btn primary sm" href="#/entdecken">{t('See suggestions')}</a>
      </Empty>
    {/if}
  </Section>
</div>
