<!-- Settings → Conversion: convert lossless files to Opus or AAC (target format, formats, quality, original afterwards …). -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Seg from '../../components/Seg.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import Toggle from './Toggle.svelte'
  import NumInput from './NumInput.svelte'
  import { S, changed, runTask } from '../../lib/state.svelte.js'
  import { toast, confirmDialog } from '../../lib/overlay.svelte.js'
  import { go } from '../../lib/router.svelte.js'
  import { api } from '../../lib/api.js'
  import { fmt } from '../../lib/format.js'
  import { t } from '../../lib/i18n.svelte.js'

  const FORMATS = [['flac', 'FLAC'], ['wav', 'WAV'], ['aiff', 'AIFF'], ['alac', 'ALAC'], ['ape', 'APE'], ['wv', 'WavPack']]

  S.config.settings.opus ??= {}
  const op = S.config.settings.opus
  S.config.settings.loudness ??= {}
  const ld = S.config.settings.loudness
  const lo = $derived(info?.loudness)

  let info = $state.raw(null)
  let error = $state('')
  const loadInfo = (refresh = false) => api(`/api/opus/info${refresh ? '?refresh=1' : ''}`).then((d) => { info = d; error = '' }).catch((e) => { error = e.message })
  loadInfo()

  const fmts = $derived(op.formats ?? ['flac'])
  const codec = $derived(op.codec || 'opus')
  function toggleFormat(id) {
    const cur = new Set(op.formats ?? ['flac'])
    cur.has(id) ? cur.delete(id) : cur.add(id)
    if (!cur.size) { toast(t('At least one format'), { error: true }); return }
    op.formats = [...cur]
    changed()
  }

  // Cancelled “delete”: redraw the selection so it shows the saved value again
  let originalKey = $state(0)
  async function setOriginal(v) {
    if (v === 'delete' && !await confirmDialog(t('Delete originals?'), t('The lossless originals are deleted after converting instead of archived. This cannot be undone.'), t('Yes, delete'), true)) { originalKey++; return }
    op.original = v
    changed()
  }

  function setOwner(e) {
    const el = e.currentTarget
    const v = el.value.trim()
    if (v && !/^\d+:\d+$/.test(v)) { toast(t('Please enter as UID:GID, e.g. 1000:1000'), { error: true }); el.value = op.owner || ''; return }
    if (v) op.owner = v
    else delete op.owner
    changed()
  }

  const startTask = (steps, opts) => runTask(steps, opts).then((ok) => { if (ok) go('#/') })
</script>

<Card title={t('Convert lossless files')} icon="headphones">
  <p class="muted small">{t('Converted music sounds like the original but takes only about a fifth of the space – ideal for phones. Every new file is fully checked before Tuttiphon touches the original; tags and cover are kept.')}</p>
  <div>
    {#if error}
      <div class="err-t small">{error}</div>
    {:else if !info}
      <div class="skel h-[60px]"></div>
    {:else}
      {#if !info.ffmpeg}
        <div class="note err-t">{t('ffmpeg/ffprobe are missing on this computer – please install them. The Docker image includes them.')}</div>
      {/if}
      {#if codec === 'aac' && info.aac === false}
        <div class="note err-t">{t('For AAC, this computer lacks a package that carries the tags over. The Docker image includes everything.')}</div>
      {/if}
      <div class="member-row">
        <Icon name={info.pending ? 'music' : 'check'} size={18} class={info.pending ? 'warn-t' : 'ok-t'} />
        <div class="flex-1 min-w-0">
          <b>{info.pending ? t('Files to convert: {n}', { n: fmt(info.pending) }) : t('Nothing to convert')}</b>
          {#if info.sample?.length}<div class="tiny muted ell">{info.sample.slice(0, 3).join(' · ')}</div>{/if}
        </div>
        <button class="btn sm ghost" onclick={() => loadInfo(true)}><Icon name="refresh" size={14} />{t('count again')}</button>
      </div>
      <div class="hint">{t('Music: {music} · Archive: {archive}', { music: info.musicDir, archive: info.archiveDir })}</div>
    {/if}
  </div>
  <Row label={t('Conversion on')}><Toggle obj={op} key="enabled" /></Row>
  <Row label={t('Target format')} hint={t('Opus is the smallest and ideal for Android. iPhone, iPad and Mac play AAC everywhere. Applies to new conversions; finished files stay as they are.')}>
    <Seg options={[['opus', 'Opus'], ['aac', 'AAC']]} value={codec} onchange={(v) => { op.codec = v; changed() }} />
  </Row>
  <Row label={t('Which formats?')} hint={t('Lossless only – .m4a only if it contains ALAC.')}>
    <div class="toggles">
      {#each FORMATS as [id, label] (id)}
        <button class={['toggle', fmts.includes(id) && 'on']} onclick={() => toggleFormat(id)}>{label}</button>
      {/each}
    </div>
  </Row>
  {#if codec === 'aac'}
    <Row label={t('Quality')} hint={t('kbit/s. AAC needs a little more than Opus for the same sound. 224 is the default, 256 for purists.')}>
      <Seg options={[['128', '128'], ['192', '192'], ['224', '224'], ['256', '256'], ['320', '320']]} value={String(op.aacBitrate || 224)} onchange={(v) => { op.aacBitrate = Number(v); changed() }} />
    </Row>
  {:else}
    <Row label={t('Quality')} hint={t('kbit/s. 128 is enough for phones, 160 is the default, 256 for purists.')}>
      <Seg options={[['96', '96'], ['128', '128'], ['160', '160'], ['192', '192'], ['256', '256']]} value={String(op.bitrate || 160)} onchange={(v) => { op.bitrate = Number(v); changed() }} />
    </Row>
  {/if}
  <Row label={t('Original afterwards')} hint={t('Only once the new file is fully checked.')}>
    {#key originalKey}
      <Seg options={[['archive', t('to the archive')], ['keep', t('keep')], ['delete', t('delete')]]} value={op.original || 'archive'} onchange={setOriginal} />
    {/key}
  </Row>
  {#if (op.original || 'archive') === 'archive'}
    <Row label={t('Archive folder')} hint={t('The folder structure is kept.')}>
      <a class="btn sm" href="#/einstellungen/speicher"><Icon name="archive" size={15} />{t('Storage locations')}</a>
    </Row>
  {/if}
  <Row label={t('Waiting time')} hint={t('Leave freshly imported files alone for this many minutes in case Lidarr is still writing.')}>
    <NumInput obj={op} key="minAgeMinutes" min={0} max={1440} placeholder="10" width={90} />
  </Row>
  <details class="fold">
    <summary><Icon name="sliders" size={16} />{t('Advanced')}</summary>
    <div class="in">
      <Row label={t('Simultaneous conversions')} hint={t('More = faster, but more load on the computer/NAS.')}>
        <NumInput obj={op} key="jobs" min={1} max={8} placeholder="1" width={90} />
      </Row>
      <Row label={t('Owner of new files')} hint={t('Empty = the user Tuttiphon runs as (user: in docker-compose.yaml). Otherwise UID:GID as in Lidarr – only works with sufficient rights.')}>
        <input class="input w-[120px]" value={op.owner || ''} placeholder="1000:1000" onchange={setOwner} />
      </Row>
    </div>
  </details>
</Card>

<Card title={t('Even out loudness')} icon="waves">
  <p class="muted small">{t('At night Tuttiphon measures how loud each song is and writes ReplayGain values into the files without re-encoding them. Turn on ReplayGain in Symfonium and all songs play equally loud, even in a mix from a children\'s song to metal.')}</p>
  <Row label={t('Leveling on')} hint={t('Writes once into every music file. Each file is copied and checked first, only then replaced. Values that already came from elsewhere stay.')}>
    <Toggle obj={ld} key="enabled" def={false} />
  </Row>
  <Row label={t('Album values too')} hint={t('For albums you listen to in one go: quiet and loud songs of an album keep their balance.')}>
    <Toggle obj={ld} key="album" def={true} />
  </Row>
  {#if lo && !lo.available}
    <div class="note">{t('Not possible here: {why}. The Docker container on the NAS includes everything.', { why: lo.why })}</div>
  {:else if lo && ld.enabled}
    <div class="hint">{t('{measured} of {songs} songs measured · {written} with values written', { measured: fmt(lo.measured), songs: fmt(lo.songs), written: fmt(lo.written) })}{lo.external ? t(' · {n} already had their own', { n: fmt(lo.external) }) : ''}.</div>
  {/if}
</Card>

<Card title={t('Run now')} icon="play">
  <div class="btns">
    <button class="btn primary sm" disabled={S.running} onclick={() => startTask(['flac'])}><Icon name="play" size={15} />{t('Convert now')}</button>
    <button class="btn sm ghost" disabled={S.running} onclick={() => startTask(['flac'], { dry_run: true })}>{t('Dry run')}</button>
  </div>
</Card>
