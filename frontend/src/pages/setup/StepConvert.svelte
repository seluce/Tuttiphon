<!-- Setup step 2: convert lossless files – off, Opus or AAC (with the bitrate) and what happens to the original
     (archive with the state of the archive folder, keep, delete with a warning). Changes only the draft d. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Card from '../settings/Card.svelte'
  import Row from '../settings/Row.svelte'
  import Choice from './Choice.svelte'
  import { S } from '../../lib/state.svelte.js'
  import { confirmDialog } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { fmt } from '../../lib/format.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { d } = $props()

  const mode = $derived(d.opus.enabled ? d.opus.codec : 'off')
  function setMode(v) {
    if (v === 'off') { d.opus.enabled = false; return }
    d.opus.enabled = true
    d.opus.codec = v
  }

  /** what is waiting in the music folder (null = loading, false = no answer) */
  let info = $state.raw(null)
  api('/api/opus/info').then((x) => { info = x }).catch(() => { info = false })

  // the archive folder as Settings → Storage locations shows it
  const archive = $derived(S.status?.paths?.archive)
  const archiveOk = $derived(!!archive?.exists && !!archive?.writable)

  // cancelled “delete”: redraw the options so they show the previous choice again
  let originalKey = $state(0)
  async function setOriginal(v) {
    if (v === 'delete' && !await confirmDialog(t('Delete originals?'), t('The lossless originals are deleted after converting instead of archived. This cannot be undone.'), t('Yes, delete'), true)) { originalKey++; return }
    d.opus.original = v
  }
</script>

<Card title={t('Convert lossless files?')} icon="headphones">
  <p class="muted small">{t('Lossless files such as FLAC are large. Converted, they sound the same to the ear but take only about a fifth of the space – ideal for phones and for listening offline.')}</p>
  <Choice name="setup-conv" value={mode} onchange={setMode} options={[
    ['off', t('Off'), t('Your files stay exactly as they are.')],
    ['opus', 'Opus', t('Smallest files, ideal for Android · {n} kbit/s', { n: d.opus.bitrate })],
    ['aac', 'AAC', t('For iPhone, iPad and Mac · {n} kbit/s', { n: d.opus.aacBitrate })],
  ]} />
  {#if d.opus.enabled}
    <div class="note grid gap-1.5">
      <span>{t('Converted are the lossless files in the music folder – FLAC, more formats under Settings → Conversion. The first run takes everything that is there, after that only new files. Files fresh from Lidarr get a few minutes of rest first.')}</span>
      <span>{t('Every new file is checked first: only when it is just as long as the original, to the second, does Tuttiphon touch the original. Tags and cover are kept.')}</span>
    </div>
    {#if info && !info.ffmpeg}
      <div class="note err-t">{t('ffmpeg/ffprobe are missing on this computer – please install them. The Docker image includes them.')}</div>
    {/if}
    {#if info && d.opus.codec === 'aac' && info.aac === false}
      <div class="note err-t">{t('For AAC, this computer lacks a package that carries the tags over. The Docker image includes everything.')}</div>
    {/if}
    {#if info === null}
      <div class="skel h-[44px]"></div>
    {:else if info && !info.error}
      <div class="member-row">
        <Icon name={info.pending ? 'music' : 'check'} size={18} class={info.pending ? 'warn-t' : 'ok-t'} />
        <b class="flex-1 min-w-0">{info.pending ? t('Files to convert: {n}', { n: fmt(info.pending) }) : t('Nothing to convert')}</b>
      </div>
    {/if}
    <Row full label={t('And the original?')} hint={t('Only once the new file is fully checked.')}>
      {#key originalKey}
        <Choice name="setup-original" value={d.opus.original} onchange={setOriginal} options={[
          ['archive', t('Move to the archive'), t('The original goes to the archive folder, in the same folder structure. The safest choice – you can always get it back.')],
          ['keep', t('Keep'), t('The original stays next to the new file. Both are then in your library, and it needs the most space.')],
          ['delete', t('Delete'), t('The original is gone for good. Only if you have a backup of your music.')],
        ]} />
      {/key}
    </Row>
    {#if d.opus.original === 'archive' && archive}
      <div class="member-row flex-wrap">
        <Icon name="archive" size={18} class={archiveOk ? 'ok-t' : 'warn-t'} />
        <div class="flex-1 min-w-[180px]">
          <b>{t('Archive folder')}</b>
          <div class="tiny muted break-all">{archive.path}</div>
        </div>
        <span class="pill {archiveOk ? 'ok' : 'warn'}">{archive.exists ? (archive.writable ? t('reachable') : t('read-only')) : t('missing')}</span>
      </div>
      {#if !archive.exists}
        <div class="hint">{t('The folder does not exist yet – Tuttiphon creates it with the first conversion if it may write there. You can choose another folder under Settings → Storage locations.')}</div>
      {:else if !archive.writable}
        <div class="hint text-warn">{t('Tuttiphon may not write to this folder, so the originals cannot be moved there. Fix the permissions or choose another folder under Settings → Storage locations.')}</div>
      {/if}
    {:else if d.opus.original === 'delete'}
      <div class="note flex gap-2.5 items-start text-warn border border-warn/40">
        <Icon name="alert" size={18} class="shrink-0 mt-0.5" />
        <span>{t('Deleted originals cannot be restored – the backup of Tuttiphon contains only its own data, not your music.')}</span>
      </div>
    {/if}
  {/if}
</Card>
