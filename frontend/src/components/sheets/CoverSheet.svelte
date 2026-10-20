<!--
  Choose a playlist's cover (sheet, opened via coverSheet() in pages/playlist/actions.js):
  designed covers as a preview, upload your own image or go back to the Navidrome default (formats get their format
  cover by themselves; after "Navidrome default" it stays away – p.cover = {style: 'none'}).
  p: playlist · d: data from /api/playlist · styles: /api/cover/styles (labels from the server, shown as they are;
  the short name ends before " aus …"/" mit …") · ondone: after a change
-->
<script>
  import { untrack } from 'svelte'
  import Icon from '../Icon.svelte'
  import { plStatus, loadPlaylists } from '../../lib/state.svelte.js'
  import { O, closeSheet, toast } from '../../lib/overlay.svelte.js'
  import { api } from '../../lib/api.js'
  import { t, lang } from '../../lib/i18n.svelte.js'

  let { p, d, styles = null, ondone = undefined } = $props()

  // Description per cover style (the keys are style ids from the server)
  const STYLE_INFO = $derived({
    format: t('Its own look for this format, renewed with every new selection'),
    mosaik: t('Four album covers with title'),
    band: t('Photo of the main band'),
    farbe: t('Color gradient with round band photos'),
    album: t('Cover of the main album'),
  })

  const mine = O.sheet   // this sheet – only close our own (not, say, the editor opened in the meantime)
  const id = untrack(() => p.id)
  const current = untrack(() => plStatus(id)?.cover?.style || (p.cover?.style !== 'none' && p.cover?.style) || null)
  const stamp = Date.now()
  let status = $state('')
  let busy = $state(false)
  let busyKey = $state(null)
  let loaded = $state({})   // style → 'ok' | 'err'
  let file = $state()

  async function done(msg) {
    const then = ondone   // props can no longer be read after closeSheet()
    toast(msg)
    if (O.sheet === mine) closeSheet()
    await loadPlaylists().catch(() => {})
    then?.()
  }
  function stop() {
    busy = false
    busyKey = null
  }

  async function apply(style) {
    busy = true
    busyKey = style
    status = t('Designing and uploading the cover …')
    try {
      await api('/api/cover/apply', { body: { id, style } })
      await done(t('Cover set ✓ – Symfonium shows it after the next sync'))
    } catch (e) { status = ''; toast(e.message, { error: true }); stop() }
  }

  async function upload(f) {
    if (!f) return
    status = t('Preparing the image …')
    busy = true
    try {
      const blob = await shrink(f)
      const res = await fetch(`/api/cover/upload?id=${encodeURIComponent(id)}`, { method: 'POST', headers: { 'X-Tuttiphon': '1', 'X-Lang': lang(), 'Content-Type': blob.type }, body: blob })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.error || res.statusText)
      await done(t('Own image set ✓'))
    } catch (e) { status = ''; toast(e.message, { error: true }); stop(); file.value = '' }
  }

  async function remove() {
    busy = true
    try {
      await api('/api/cover/remove', { body: { id } })
      await done(t('Navidrome shows its default image again'))
    } catch (e) { toast(e.message, { error: true }); stop() }
  }

  /** Shrink large phone photos before uploading (max. 1200 px, JPEG). */
  async function shrink(f) {
    if (!/^image\/(jpeg|png|webp)$/.test(f.type)) throw new Error(t('Please choose a JPG, PNG or WebP image'))
    let bmp
    try { bmp = await createImageBitmap(f) } catch { throw new Error(t('The image cannot be opened')) }
    const scale = Math.min(1, 1200 / Math.max(bmp.width, bmp.height))
    if (scale === 1 && f.size < 3 * 1024 * 1024) { bmp.close?.(); return f }
    const c = document.createElement('canvas')
    c.width = Math.round(bmp.width * scale)
    c.height = Math.round(bmp.height * scale)
    const g = c.getContext('2d')
    g.fillStyle = '#fff'   // keep transparent PNGs from turning black
    g.fillRect(0, 0, c.width, c.height)
    g.drawImage(bmp, 0, 0, c.width, c.height)
    bmp.close?.()
    return await new Promise((res, rej) => c.toBlob((b) => (b ? res(b) : rej(new Error(t('The image could not be shrunk')))), 'image/jpeg', 0.9))
  }
</script>

{#if !d.navidrome}
  <div class="note">{t('The playlist is not in Navidrome yet. As soon as it is applied, you can choose a cover here.')}</div>
{:else}
  <div class="grid gap-[18px]">
    <p class="muted small">{t('The image appears in Navidrome and – after the next sync – in Symfonium. Tuttiphon renews designed covers by itself when the playlist changes – so for mixes with every new selection.')}</p>
    <div class="cover-grid">
      {#each Object.entries(styles || {}) as [k, label] (k)}
        <button type="button" class="cover-opt" class:on={current === k} class:busy={busyKey === k} disabled={busy || loaded[k] === 'err'}
          onclick={() => apply(k)}>
          <div class="ph" class:skel={!loaded[k]}>
            {#if loaded[k] === 'err'}
              <span class="tiny muted p-2.5 text-center">{t('not possible here')}</span>
            {:else}
              <img alt={label} class:hidden={!loaded[k]} src="/cover?id={encodeURIComponent(id)}&style={k}&t={stamp}"
                onload={() => (loaded[k] = 'ok')} onerror={() => (loaded[k] = 'err')} />
            {/if}
          </div>
          <div>
            <b>{label.replace(/ aus .*| mit .*/, '')}</b>
            {#if current === k}<span class="pill ok ml-1.5">{t('active')}</span>{/if}
          </div>
          <div class="tiny muted">{STYLE_INFO[k] || label}</div>
        </button>
      {/each}
    </div>
    <div class="btns">
      <button class="btn" class:primary={current === 'eigenes'} disabled={busy} onclick={() => file.click()}>
        <Icon name="upload" size={17} />{current === 'eigenes' ? t('Another own image') : t('Upload own image')}
      </button>
      {#if current}
        <button class="btn ghost" disabled={busy} onclick={remove}><Icon name="undo" size={17} />{t('Navidrome default')}</button>
      {/if}
      <input bind:this={file} type="file" accept="image/jpeg,image/png,image/webp" hidden onchange={() => upload(file.files[0])} />
    </div>
    <div class="small muted">{status}</div>
  </div>
{/if}

<style>
  .cover-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .cover-opt { display: grid; gap: 6px; padding: 6px; border-radius: var(--radius-card); border: 2px solid transparent; background: none; color: inherit; font: inherit; cursor: pointer; text-align: left; }
  .cover-opt:hover { background: var(--surface-2); }
  .cover-opt.on { border-color: var(--accent); }
  .cover-opt.busy { opacity: .6; pointer-events: none; }
  .ph { aspect-ratio: 1; border-radius: calc(var(--radius-card) - 2px); background: var(--surface-3); overflow: hidden; display: grid; place-items: center; }
  img { width: 100%; height: 100%; object-fit: cover; }
</style>
