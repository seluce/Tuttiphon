<!-- Settings → Storage locations: music, playlist and archive folders (in the container from docker-compose.yaml, then view only). -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Card from './Card.svelte'
  import { S, changed, loadStatus } from '../../lib/state.svelte.js'
  import { toast, confirmDialog } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { t } from '../../lib/i18n.svelte.js'

  const LABEL = $derived({
    music: ['disc', t('Music'), t('The folder Navidrome also uses as its library. Converted files and lyrics are created here.')],
    playlists: ['playlists', t('Playlists'), t('Must be inside the music folder, otherwise Navidrome does not read them. Relative = inside the music folder, e.g. “00_SmartPlaylists”.')],
    archive: ['archive', t('Archive'), t('Where the originals go after converting. Relative = next to the music folder, e.g. “Archiv”.')],
  })
  const ENV_NAME = { music: 'MUSIC_DIR', playlists: 'PLAYLIST_DIR', archive: 'ARCHIVE_DIR' }

  S.config.settings.paths ??= {}
  const conf = S.config.settings.paths
  const info = $derived(S.status?.paths || {})
  const isLocked = (key) => info[key]?.source === 'docker'

  const inputs = $state({ music: conf.music || '', playlists: conf.playlists || '', archive: conf.archive || '' })
  let result = $state({ text: '', cls: '' })

  const values = () => Object.fromEntries(Object.keys(LABEL).filter((k) => !isLocked(k)).map((k) => [k, inputs[k].trim()]))

  async function check() {
    result = { text: t('checking …'), cls: 'muted' }
    const r = await api('/api/paths/check', { body: values() }).catch((e) => ({ error: e.message }))
    if (r.error) { result = { text: r.error, cls: 'err-t' }; return false }
    const bad = Object.entries(r).filter(([, i]) => !i.exists || !i.writable).map(([k]) => LABEL[k][1])
    const outside = r.playlists && !r.playlists.insideMusic
    result = {
      cls: bad.length || outside ? 'err-t' : 'ok-t',
      text: outside ? t('✕ The playlist folder must be inside the music folder.') : bad.length ? t('✕ Not reachable or not writable: {folders}', { folders: bad.join(', ') }) : t('✓ All folders reachable and writable.'),
    }
    return !bad.length && !outside
  }

  async function saveIt() {
    if (!await check() && !await confirmDialog(t('Save anyway?'), t('Not all folders are reachable. Tuttiphon only works properly again once they are.'), t('Save'))) return
    const v = values()
    for (const k of Object.keys(v)) { if (v[k]) conf[k] = v[k]; else delete conf[k] }
    changed()
    toast(t('Storage locations saved ✓'))
    setTimeout(() => loadStatus(), 1200)
  }
</script>

{#snippet badge(i)}
  {#if i?.source === 'docker'}<span class="pill">{t('from docker-compose')}</span>
  {:else if i?.source === 'einstellung'}<span class="pill acc">{t('own setting')}</span>
  {:else}<span class="pill">{t('Default')}</span>{/if}
{/snippet}

<Card title={t('Where is what?')} icon="drive">
  <p class="muted small">{t('Normally everything fits on its own. In the Docker container you set the folders as volumes in docker-compose.yaml – then they are shown here for viewing only.')}</p>
  {#each Object.entries(LABEL) as [key, [icon, label, hint]] (key)}
    {@const i = info[key] || {}}
    <div class="grid grid-cols-[32px_minmax(0,1fr)] gap-3.5 py-3 border-t border-line">
      <div class="hi"><Icon name={icon} size={18} /></div>
      <div class="min-w-0 grid gap-1.5">
        <div class="btns">
          <b>{label}</b>
          {@render badge(i)}
          {#if i.path}
            <span class="pill {i.exists && i.writable ? 'ok' : 'warn'}">{i.exists ? (i.writable ? t('reachable') : t('read-only')) : t('missing')}</span>
          {/if}
        </div>
        {#if i.path && !i.exists}<div class="hint text-warn">{t('The folder does not exist yet – create it or choose another one.')}</div>{/if}
        <input class="input w-full" bind:value={inputs[key]} placeholder={i.path || ''} disabled={isLocked(key)} />
        <div class="hint">{isLocked(key) ? t('Set in docker-compose.yaml as {name} – change it there.', { name: ENV_NAME[key] }) : hint}</div>
        <div class="tiny muted ell">{t('current: {path}', { path: i.path || '–' })}</div>
      </div>
    </div>
  {/each}
  <div class="btns">
    <button class="btn" onclick={check}>{t('Check')}</button>
    <button class="btn primary" onclick={saveIt}>{t('Save')}</button>
    <div class="small {result.cls}">{result.text}</div>
  </div>
  <div class="hint">{t('Leave empty = default. Configuration, credentials and logs are in the Tuttiphon data folder, in the container under /config.')}</div>
</Card>
