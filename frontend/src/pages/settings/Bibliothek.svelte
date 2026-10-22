<!-- Settings → Check library: what helps with tidying up (/api/pflege). Read only – nothing is changed.
     “Same recording twice” (audio fingerprints) also lists the copies of each group; tapping one opens the song window. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Avatar from '../../components/Avatar.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import Toggle from './Toggle.svelte'
  import { S, runTask } from '../../lib/state.svelte.js'
  import { go } from '../../lib/router.svelte.js'
  import { api } from '../../lib/api.js'
  import { openArtist } from '../../lib/artist.js'
  import { openSong } from '../../lib/song.js'
  import { fmt, mmss } from '../../lib/format.js'
  import { t } from '../../lib/i18n.svelte.js'

  S.config.settings.covers ??= { enabled: true }
  const cv = S.config.settings.covers
  const fetchNow = () => runTask(['cover', 'scan']).then((ok) => { if (ok) go('#/') })

  const ICONS = { doppelt: 'copy', mehrfach: 'repeat', aufnahme: 'fingerprint', cover: 'image', luecken: 'list', kurz: 'clock', genre: 'music', qualitaet: 'headphones' }
  /** fingerprinting still running (check “aufnahme”): no “all good” yet */
  const unfinished = (c) => !!c.progress && c.progress.done < c.progress.total
  /** a copy of “Same recording twice” as a song for the song window */
  const asTrack = (x) => ({ id: x.id, title: x.title, artist: x.artist, album: x.album, duration: x.duration, cover: x.albumId ? `al-${x.albumId}` : null })

  /** null = loading, false = error */
  let data = $state.raw(null)
  let error = $state('')
  const load = () => {
    data = null
    api('/api/pflege').then((d) => { data = d }).catch((e) => { data = false; error = e.message })
  }
  load()
</script>

<Card title={t('Check library')} icon="eraser">
  <p class="muted small">{t('What helps with tidying up: duplicates, missing covers, gaps in albums and unusual files. This only shows things – nothing is changed. Tap a band to open it.')}</p>
  {#if data === null}
    <div class="skel h-[120px]"></div>
  {:else if data === false}
    <p class="err-t small">{error || t('The check could not be loaded.')}</p>
  {:else}
    <div class="flex gap-3 items-center justify-between">
      <span class="small muted">{t('{songs} songs in {albums} albums checked', { songs: fmt(data.songs), albums: fmt(data.albums) })}</span>
      <button class="btn sm" onclick={load}><Icon name="refresh" size={15} />{t('Check again')}</button>
    </div>
    <div class="grid grid-cols-[minmax(0,1fr)] gap-2.5">   <!-- minmax: long names are cut off instead of widening the page -->
      {#each data.checks as c (c.id)}
        <details class="fold">
          <summary>
            <span class="hi"><Icon name={ICONS[c.id] || 'info'} size={18} /></span>
            <span class="flex-1 min-w-0">{c.title}<span class="block tiny muted font-normal">{c.text}</span>
              {#if unfinished(c)}<span class="block tiny muted font-normal">{t('So far {done} of {total} songs compared – the rest follows night after night.', { done: fmt(c.progress.done), total: fmt(c.progress.total) })}</span>{/if}
            </span>
            <span class="pill" class:ok={!c.count && !unfinished(c)}>{c.count ? fmt(c.count) : unfinished(c) ? t('none so far') : t('all good')}</span>
          </summary>
          {#if c.items.length}
            <div class="in">
              <div class="grid grid-cols-[minmax(0,1fr)] gap-1">
                {#each c.items as x, i (i)}
                  <div class="flex gap-3 items-center py-1">
                    <button type="button" class="contents cursor-pointer" onclick={() => openArtist(x.artist)} title={x.artist}>
                      <Avatar name={x.artist || '?'} id={x.artistId} size={30} />
                    </button>
                    <div class="flex-1 min-w-0">
                      <div class="ell">{x.title || x.album || x.artist}</div>
                      <div class="tiny muted ell">{[x.artist, x.title ? x.album : null].filter(Boolean).join(' · ')}</div>
                    </div>
                    <span class="tiny muted shrink-0 text-right max-w-[45%] ell">{x.detail}</span>
                  </div>
                  {#if x.copies?.length}
                    <div class="grid gap-1.5 ml-[15px] mb-2 pl-[25px] border-l-2 border-line">
                      {#each x.copies as cp (cp.id)}
                        <div class="min-w-0">
                          <button type="button" class="block max-w-full ell text-left font-semibold text-[.88rem] cursor-pointer hover:text-accent" onclick={() => openSong(asTrack(cp))}>{cp.title}</button>
                          <div class="tiny muted">{[cp.format, cp.bitRate ? `${cp.bitRate} kbit/s` : null, mmss(cp.duration), cp.album].filter(Boolean).join(' · ')}</div>
                          {#if cp.path}<div class="tiny muted wrap-anywhere">{cp.path}</div>{/if}
                        </div>
                      {/each}
                    </div>
                  {/if}
                {/each}
                {#if c.count > c.items.length}<div class="tiny muted">{t('… and {n} more', { n: fmt(c.count - c.items.length) })}</div>{/if}
                {#if c.id === 'aufnahme'}<div class="hint mt-1">{t('Remove the extra copies from the music folder yourself – tapping a copy opens it to listen in. Navidrome notices the change at its next scan.')}</div>{/if}
              </div>
            </div>
          {/if}
        </details>
      {/each}
    </div>
    {#if data.fingerprints?.available && data.fingerprints.enabled && !data.fingerprints.comparedAt}
      <div class="note">{t('“Same recording twice” appears here once the audio fingerprints have been compared – they are made during “Understand music” and at night.')}</div>
    {/if}
  {/if}
</Card>

<Card title={t('Missing covers')} icon="image">
  <p class="muted small">{t('For albums without any picture, Tuttiphon fetches a cover – from the Cover Art Archive via the MusicBrainz ID, otherwise from Deezer – and places it as cover.jpg next to the music. Existing pictures stay, and new albums get two days so Lidarr can place its own.')}</p>
  <Row label={t('Fetch missing covers automatically')} hint={t('During “Update everything” and once a week in the time window of the night analysis. Anything not found is tried again after 30 days.')}>
    <Toggle label={t('Fetch missing covers automatically')} obj={cv} key="enabled" />
  </Row>
  <div class="btns"><button class="btn sm" disabled={S.running || cv.enabled === false} onclick={fetchNow}><Icon name="image" size={15} />{t('Fetch now')}</button></div>
</Card>
