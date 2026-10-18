<!--
  Song list to listen to: tapping plays the song in the mini player (lib/player.svelte.js) and then the rest of the
  list; "…" opens the song sheet, the band name the band sheet. The playing song is highlighted.
  fold: on the phone this many songs first, then "Show all". compact: only cover, title/band and length.
-->
<script>
  import Icon from './Icon.svelte'
  import Cover from './Cover.svelte'
  import { MOODS } from '../lib/state.svelte.js'
  import { mmss, stars } from '../lib/format.js'
  import { openArtist } from '../lib/artist.js'
  import { openSong } from '../lib/song.js'
  import { player, playList, isCurrent } from '../lib/player.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  let { tracks = [], from = '', fold = 0, compact = false } = $props()
  let all = $state(false)
  const folded = $derived(fold > 0 && !all && tracks.length > fold)
</script>

<div class="tracks">
  {#each tracks as tr, i (i)}
    {@const on = isCurrent(tr.id)}
    <!-- the whole row plays: a button lies over it; band name and "…" are buttons of their own above it
         (no buttons inside a button) -->
    <div class="trk play-row" class:compact class:on class:hide-m={folded && i >= fold}>
      <button type="button" class="hit" aria-label={t('Play {title}', { title: tr.title })} onclick={() => playList(tracks, i, from)}></button>
      {#if !compact}
        <span class="no">
          {#if on && player.playing}<Icon name="waves" size={16} class="text-accent" />{:else}<span class="nr">{i + 1}</span><Icon name="play" size={15} class="pl" />{/if}
        </span>
      {/if}
      <span class="relative">
        <Cover id={tr.cover} size={compact ? 40 : 44} />
        <span class="cov-play"><Icon name={on && player.playing ? 'waves' : 'play'} size={16} /></span>
      </span>
      <div class="min-w-0">
        <div class="tt ell">{tr.title}</div>
        <div class="sub ell">
          <button type="button" class="band" onclick={() => openArtist(tr.artist)}>{tr.artist}</button>{#if tr.bpm && !compact}<span class="snd">{` · ${tr.bpm} BPM` + (tr.moods?.length ? ` · ${MOODS[tr.moods[0]] || tr.moods[0]}` : '')}</span>{/if}
        </div>
      </div>
      {#if !compact}
        <span class="sub ell alb">{(tr.album || '') + (tr.year ? ` · ${tr.year}` : '')}</span>
        <span class="stars">{stars(tr.rating)}</span>
      {/if}
      <span class="dur">{mmss(tr.duration)}</span>
      <button type="button" class="more" aria-label={t('More about {title}', { title: tr.title })} title={t('More about the song')}
        onclick={() => openSong(tr)}><Icon name="more" size={18} /></button>
    </div>
  {/each}
</div>
{#if folded}
  <button type="button" class="btn sm ghost mt-1.5 hidden max-mobile:inline-flex" onclick={() => (all = true)}>
    <Icon name="down" size={16} />{t('Show all {n}', { n: tracks.length })}
  </button>
{/if}

<style>
  .play-row { cursor: pointer; position: relative; }
  .hit { position: absolute; inset: 0; z-index: 1; border: 0; padding: 0; background: none; border-radius: 10px; cursor: pointer; }
  .hit:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .band, .more { position: relative; z-index: 2; }
  .band { border: 0; padding: 0; background: none; font: inherit; color: inherit; cursor: pointer; max-width: 100%;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: bottom; text-align: left; }
  .band:hover { text-decoration: underline; }
  .band:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; border-radius: 4px; }
  .play-row.on .tt { color: var(--accent); }
  .play-row :global(.pl) { display: none; margin-left: auto; color: var(--text); }
  .play-row:hover .nr { display: none; }
  .play-row:hover :global(.pl) { display: block; }
  .no { display: flex; justify-content: flex-end; align-items: center; }
  .compact { grid-template-columns: 40px minmax(0, 1fr) 46px 32px; }
  .cov-play { position: absolute; inset: 0; display: grid; place-items: center; border-radius: 8px; color: #fff;
    background: rgba(5, 5, 12, .45); opacity: 0; transition: opacity .15s; }
  .compact:hover .cov-play, .compact.on .cov-play { opacity: 1; }
  .more { display: grid; border: 0; background: none; place-items: center; width: 32px; height: 32px; border-radius: 9px; color: var(--muted); }
  .more:hover { background: var(--surface); color: var(--text); }
  @media (max-width: 900px) {
    .hide-m { display: none; }
    .no { display: none; }
    .play-row.on .cov-play { opacity: 1; }
    .compact { grid-template-columns: 40px minmax(0, 1fr) 44px 32px; }
  }
</style>
