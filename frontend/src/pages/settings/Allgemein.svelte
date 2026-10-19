<!-- Settings → General: theme, install as app, setup assistant (administrators), about Tuttiphon. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Seg from '../../components/Seg.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import { S, isAdmin, changed, reloadConfig, reloadTexts } from '../../lib/state.svelte.js'
  import { themeChoice, setTheme } from '../../lib/theme.js'
  import { LANGUAGES, choice as langChoice, setLanguage, t } from '../../lib/i18n.svelte.js'
  import { api } from '../../lib/api.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { install, standalone as isStandalone, ios as isIos, secure as isSecure } from '../../lib/install.svelte.js'

  const env = $derived(S.status?.env || {})
  const inst = $derived(S.status?.instance || {})

  let changes = $state.raw([])
  if (isAdmin()) api('/api/changelog').then((c) => (changes = c)).catch(() => {})

  /** Switch the interface language right away (no reload) and fetch the server's texts in it. */
  let langPick = $state(langChoice())
  async function setInterfaceLanguage(v) {
    langPick = v
    let switched
    try {
      switched = await setLanguage(v)
    } catch {
      langPick = langChoice()   // the saved choice stays – and so does the language on the screen
      toast(t('The language could not be loaded. Please try again shortly.'), { error: true })
      return
    }
    if (switched) await reloadTexts()
  }

  /** Save at once and reload: the server renames the delivered vibes into the new language. */
  async function setServerLanguage(v) {
    S.config.settings.language = v
    changed()
    await reloadConfig()   // saves first
  }

  const standalone = isStandalone()
  const ios = isIos()
  const secure = isSecure()
</script>

<Card title={t('Appearance')} icon="palette">
  <Row label={t('Theme')} hint={t('“System” follows the setting of your phone or computer.')}>
    <Seg options={[['system', t('System')], ['light', t('Light')], ['dark', t('Dark')]]} value={themeChoice()} onchange={setTheme} />
  </Row>
  <Row label={t('Language')} hint={t('Automatic follows the language of the browser. Applies to this device.')}>
    <Seg options={[['auto', t('Automatic')], ...LANGUAGES.map((l) => [l.key, l.name])]} value={langPick} onchange={setInterfaceLanguage} />
  </Row>
  {#if isAdmin()}
    <Row label={t('Language of the server')} hint={t('For run logs, notifications and the names Tuttiphon gives playlists and music worlds by itself. Delivered vibes that still have their original name are renamed too.')}>
      <Seg options={LANGUAGES.map((l) => [l.key, l.name])} value={S.config.settings.language || 'en'} onchange={setServerLanguage} />
    </Row>
  {/if}
</Card>

<Card title={t('Install as app')} icon="smartphone">
  {#if standalone}
    <p class="ok-t">{t('✓ Tuttiphon is running as an app right now.')}</p>
  {:else}
    <div class="grid gap-3">
      {#if S.installPrompt}
        <div><button class="btn primary" onclick={install}><Icon name="plus" size={16} />{t('Install Tuttiphon')}</button></div>
      {/if}
      <ul class="small grid gap-2 pl-5 my-[1em] list-disc">
        {#if ios}
          <li>{@html t('iPhone/iPad: in Safari, tap <b>Share</b> → <b>Add to Home Screen</b>.')}</li>
        {:else if secure}
          <li>{@html t('Android/Chrome: menu <b>⋮</b> → <b>Install app</b>.')}</li>
        {:else}
          <li>{@html t('Android/Chrome: menu <b>⋮</b> → <b>Add to Home screen</b>.')}</li>
        {/if}
        <li>{t('Computer: in Chrome/Edge, click the install icon on the right of the address bar.')}</li>
      </ul>
      {#if !secure}
        {#if isAdmin()}
          <div class="note">{t('Note: Over a plain http address like http://192.168.1.10:8765, the phone only creates a shortcut. A “real” app with its own window needs https – e.g. via a reverse proxy on the NAS with a certificate, such as Nginx Proxy Manager as a container.')}</div>
        {:else}
          <div class="note">{t('Note: With this address, the phone only creates a shortcut – that is perfectly fine. The administrator can set up a “real” app with its own window.')}</div>
        {/if}
      {/if}
    </div>
  {/if}
</Card>

{#if isAdmin()}
  <Card title={t('Setup assistant')} icon="wand">
    <Row label={t('Run the setup assistant again')} hint={t('Goes through the most important settings once more: connection, conversion, lyrics, understanding music, Deezer stars and what runs by itself. Apart from the connection, nothing changes until you tap “Finish”.')}>
      <a class="btn sm" href="#/einrichtung"><Icon name="wand" size={15} />{t('Start')}</a>
    </Row>
  </Card>
{/if}

<Card title={t('About Tuttiphon')} icon="info">
  <p class="small"><b>{t('Version {version}', { version: S.status?.version || '…' })}</b></p>
  <p class="muted small">{@html t('Free software under the AGPL-3.0 – <a class="link" href="https://github.com/seluce/tuttiphon" target="_blank" rel="noopener">source code on GitHub</a>')}</p>
  {#if isAdmin()}
    <p class="muted small">{[
      inst.docker ? t('Runs in the Docker container') : t('Runs on this computer'),
      inst.others?.length ? t('another instance active: {hosts}', { hosts: inst.others.map((o) => o.host).join(', ') }) : '',
      env.auth ? t('Sign-in with the Navidrome account or as local administrator') : t('Sign-in turned off, reachable only from this computer'),
    ].filter(Boolean).join(' · ')}</p>
    <p class="muted small">{t('Settings, credentials and logs are in the Tuttiphon data folder, in the container under /config.')} <a class="link" href="#/hilfe/docker">{t('Setup on the NAS →')}</a></p>
    {#if changes.length}
      <details class="fold">
        <summary><Icon name="list" size={18} />{t('What’s new?')}</summary>
        <div class="in grid gap-3.5">
          {#each changes.slice(0, 5) as v (v.version)}
            <div>
              <b>{v.unreleased ? t('Not released yet') : v.version}</b>{#if v.date}<span class="muted small"> · {v.date}</span>{/if}
              <!-- levels (parallel to items): 1 = a sub-point of the point above it -->
              <ul class="list-disc pl-5 mt-1 grid gap-0.5 small text-text-2">{#each v.items as item, i (i)}<li class={v.levels?.[i] === 1 ? 'ml-5 list-[circle]' : ''}>{item}</li>{/each}</ul>
            </div>
          {/each}
        </div>
      </details>
    {/if}
  {/if}
</Card>
