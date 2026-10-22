<!-- "Library" card (start page): file formats, albums still in MP3, favorites. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import { S } from '../../lib/state.svelte.js'
  import { fmt, plural } from '../../lib/format.js'
  import { t, tn } from '../../lib/i18n.svelte.js'

  const L = $derived(S.library)
  const total = $derived(L?.songs || 1)
</script>

<div class="card">
  {#if L}
    <div class="card-head">
      <h2><span class="hi"><Icon name="disc" size={18} /></span>{t('Library')}</h2>
      <span class="muted small">{plural(L.genres.length, 'genre', 'genres')}</span>
    </div>
    <div class="grid gap-2">
      {#each Object.entries(L.suffix).sort((a, b) => b[1] - a[1]) as [k, n] (k)}
        <div class="hbar">
          <b>{k.toUpperCase()}</b>
          <div class="tr"><i style:width="{Math.max(1, (n / total) * 100)}%"></i></div>
          <span class="n">{fmt(n)}</span>
        </div>
      {/each}
    </div>
    {#if L.mp3Albums.length}
      <details class="small mt-3.5">
        <summary class="muted cursor-pointer">{tn(L.mp3Albums.length, '{n} album still in MP3 – list', '{n} albums still in MP3 – list')}</summary>
        <ul class="max-h-[200px] overflow-auto pl-[18px] list-disc">
          {#each L.mp3Albums as a, i (i)}<li>{a}</li>{/each}
        </ul>
      </details>
    {/if}
    <p class="muted small mt-3">{t('{loved} favorites · {played} songs with plays', { loved: fmt(L.loved), played: fmt(L.played) })}</p>
  {/if}
</div>
