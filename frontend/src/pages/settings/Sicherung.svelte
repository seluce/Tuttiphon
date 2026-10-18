<!-- Settings → Backup: daily backup of configuration, credentials and state (app/backup.py). -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import Toggle from './Toggle.svelte'
  import NumInput from './NumInput.svelte'
  import { S, changed } from '../../lib/state.svelte.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { fmt, relTime } from '../../lib/format.js'
  import { t, locale } from '../../lib/i18n.svelte.js'

  S.config.settings.backup ??= {}
  const bk = S.config.settings.backup

  let info = $state(null)
  let error = $state('')
  let busy = $state(false)
  let dir = $state(bk.dir || '')

  const load = () => api('/api/backups').then((d) => { info = d; error = '' }).catch((e) => { error = e.message })
  load()

  async function now() {
    busy = true
    try {
      const r = await api('/api/backups/now', { body: {} })
      toast(t('Backed up ✓ – {size} KB', { size: fmt(Math.round(r.size / 1024)) }))
      await load()
    } catch (e) {
      toast(e.message, { error: true })
    }
    busy = false
  }
  function saveDir() {
    const v = dir.trim()
    if (v) bk.dir = v
    else delete bk.dir
    changed()
    setTimeout(load, 900)   // check the new folder after saving
  }
  const size = (b) => (b >= 1048576 ? `${(b / 1048576).toLocaleString(locale(), { minimumFractionDigits: 1, maximumFractionDigits: 1 })} MB` : `${fmt(Math.round(b / 1024))} KB`)
  const when = (iso) => new Date(iso).toLocaleString(locale(), { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
</script>

<Card title={t('Backup')} icon="archive">
  <p class="muted small">
    {t('Once a day, at the time of the daily refresh, Tuttiphon backs up everything that cannot be restored on its own: settings, people, music worlds and playlists, credentials, Deezer status, sound analysis, listening history for the recap and the saved original playlists. Not images and logs.')}
  </p>
  <Row label={t('Back up daily')}><Toggle obj={bk} key="enabled" /></Row>
  <Row label={t('Keep')} hint={t('This many backups are kept – the oldest are deleted.')}>
    <span class="flex items-center gap-2"><NumInput obj={bk} key="keep" min={1} max={365} placeholder="14" width={90} /> {t('copies')}</span>
  </Row>
  <Row label={t('Folder')} hint={t('Empty = default: in the Docker container the folder from docker-compose.yaml, e.g. “/backup” on another disk, otherwise the data folder. Best on a different disk than the settings. Relative = inside the Navidrome folder.')} full>
    <div class="flex flex-wrap gap-2 items-center">
      <input class="input flex-1 min-w-[220px]" placeholder={t('Default: in the data folder')} bind:value={dir} onchange={saveDir} />
      {#if info}
        <span class="small {info.writable ? 'ok-t' : 'err-t'}">{info.writable ? t('✓ writable') : t('✕ not writable')}</span>
      {/if}
    </div>
    {#if info}<div class="tiny muted">{t('In use: {path}', { path: info.path })}</div>{/if}
  </Row>
</Card>

<Card title={t('Existing backups')} icon="clock">
  {#if error}
    <p class="err-t small">{error}</p>
  {:else if !info}
    <p class="muted small">{t('Loading backups …')}</p>
  {:else}
    <div class="btns">
      <button class="btn primary sm" onclick={now} disabled={busy}><Icon name="archive" size={16} />{busy ? t('Backing up …') : t('Back up now')}</button>
      {#if info.last}<span class="muted small">{t('Latest: {when}', { when: relTime(info.last.time) })}</span>{/if}
    </div>
    {#if info.items.length}
      <div class="grid gap-1.5">
        {#each info.items as x (x.name)}
          <div class="flex items-center gap-3 px-3 py-2 rounded-xl bg-surface-2">
            <Icon name="archive" size={18} class="text-accent shrink-0" />
            <div class="flex-1 min-w-0"><div class="ell">{when(x.time)}</div><div class="tiny muted">{size(x.size)}</div></div>
            <a class="btn sm" href="/api/backups/file?name={encodeURIComponent(x.name)}" download>{t('Download')}</a>
          </div>
        {/each}
      </div>
    {:else}
      <p class="muted small">{t('No backup yet.')}</p>
    {/if}
    <details class="fold">
      <summary><Icon name="undo" size={18} />{t('Restore')}</summary>
      <div class="in small text-text-2">
        <ol class="list-decimal pl-5 grid gap-1.5">
          <li>{t('Quit Tuttiphon or stop the Docker container.')}</li>
          <li>{@html t('Unpack the chosen ZIP backup into the data folder – in the container, that is the folder mounted as <code>/config</code>. Overwrite existing files.')}</li>
          <li>{t('Start Tuttiphon again. After that, everyone signs in once more.')}</li>
        </ol>
        <p class="hint">{t('The backup contains credentials – keep it in safe places only.')}</p>
      </div>
    </details>
  {/if}
</Card>
