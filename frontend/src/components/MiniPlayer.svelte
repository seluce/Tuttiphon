<!--
  Mini player (lib/player.svelte.js): appears as soon as a song plays – on the computer as a bar at the bottom, on
  the phone above the navigation. Tapping the title or cover opens the song sheet. Sets --player to its own height so
  the apply bar, notes and the end of the page stay above it.
-->
<script>
  import Icon from './Icon.svelte'
  import Cover from './Cover.svelte'
  import { player, current, toggle, next, prev, seek, stop } from '../lib/player.svelte.js'
  import { openSong } from '../lib/song.js'
  import { mmss } from '../lib/format.js'
  import { t } from '../lib/i18n.svelte.js'

  const song = $derived(current())
  const pct = $derived(player.dur ? Math.min(100, (player.time / player.dur) * 100) : 0)

  $effect(() => {
    document.documentElement.style.setProperty('--player', song ? 'var(--player-h)' : '0px')
  })
</script>

{#if song}
  <div class="mini" role="region" aria-label={t('Playback')}>
    <button type="button" class="who" onclick={() => openSong(song)} title={t('More about the song')}>
      <Cover id={song.cover} size={44} />
      <span class="min-w-0 grid text-left">
        <b class="ell">{song.title}</b>
        {#if player.error}<span class="ell err">{t('This song cannot be played right now.')}</span>{:else}<span class="ell muted small">{song.artist}</span>{/if}
      </span>
    </button>
    <div class="ctl">
      <button type="button" class="ib max-mobile:hidden" aria-label={t('Previous song')} onclick={prev}><Icon name="skip-back" size={18} /></button>
      <button type="button" class="ib main" aria-label={player.playing ? t('Pause') : t('Play')} onclick={toggle}>
        {#if player.loading && !player.error}<Icon name="loader" size={20} class="animate-spin" />{:else}<Icon name={player.playing ? 'pause' : 'play'} size={20} />{/if}
      </button>
      <button type="button" class="ib" aria-label={t('Next song')} disabled={player.i >= player.queue.length - 1} onclick={() => next()}><Icon name="skip-forward" size={18} /></button>
    </div>
    <div class="pos">
      <span class="tm max-mobile:hidden">{mmss(player.time) || '0:00'}</span>
      <input type="range" min="0" max={Math.max(1, Math.round(player.dur))} step="1" value={Math.round(player.time)}
        style:--pct="{pct}%" aria-label={t('Position in the song')} oninput={(e) => seek(Number(e.currentTarget.value))} />
      <span class="tm max-mobile:hidden">{mmss(player.dur) || ''}</span>
    </div>
    <button type="button" class="ib" aria-label={t('Stop playback')} title={t('Close')} onclick={stop}><Icon name="x" size={18} /></button>
  </div>
{/if}

<style>
  .mini {
    position: fixed; left: var(--sidebar); right: 0; bottom: 0; z-index: 36; height: var(--player-h);
    display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1.3fr) auto; align-items: center; gap: 16px;
    padding: 0 20px; background: var(--bg-2); border-top: 1px solid var(--line); box-shadow: 0 -10px 30px rgba(0, 0, 0, .25);
  }
  .who { display: flex; align-items: center; gap: 12px; min-width: 0; cursor: pointer; }
  .err { font-size: .8rem; color: var(--err); }
  .ctl { display: flex; align-items: center; gap: 6px; }
  .ib { display: grid; place-items: center; width: 36px; height: 36px; border-radius: 50%; color: var(--text); cursor: pointer; }
  .ib:hover:not(:disabled) { background: var(--surface); }
  .ib:disabled { opacity: .35; cursor: default; }
  .ib.main { width: 42px; height: 42px; background: var(--text); color: var(--bg); }
  .ib.main:hover { background: var(--text); opacity: .9; }
  .pos { display: flex; align-items: center; gap: 10px; min-width: 0; }
  .tm { font-size: .78rem; color: var(--muted); font-variant-numeric: tabular-nums; min-width: 34px; text-align: center; }
  input[type='range'] {
    flex: 1; min-width: 0; height: 18px; appearance: none; background: transparent; cursor: pointer; margin: 0;
  }
  input[type='range']::-webkit-slider-runnable-track {
    height: 4px; border-radius: 4px; background: linear-gradient(90deg, var(--accent) var(--pct), var(--line-2) var(--pct));
  }
  input[type='range']::-moz-range-track { height: 4px; border-radius: 4px; background: var(--line-2); }
  input[type='range']::-moz-range-progress { height: 4px; border-radius: 4px; background: var(--accent); }
  input[type='range']::-webkit-slider-thumb { appearance: none; width: 12px; height: 12px; margin-top: -4px; border-radius: 50%; background: var(--text); }
  input[type='range']::-moz-range-thumb { width: 12px; height: 12px; border: 0; border-radius: 50%; background: var(--text); }

  @media (max-width: 900px) {
    .mini {
      left: 8px; right: 8px; bottom: calc(66px + env(safe-area-inset-bottom)); border: 1px solid var(--line-2);
      border-radius: 16px; padding: 0 6px 0 8px; gap: 4px; grid-template-columns: minmax(0, 1fr) auto auto;
    }
    .who { gap: 10px; }
    .who :global(img), .who :global(.cover) { width: 40px; height: 40px; }
    .pos { position: absolute; left: 16px; right: 16px; bottom: -2px; }
    input[type='range'] { height: 14px; }
    input[type='range']::-webkit-slider-runnable-track { height: 3px; }
    input[type='range']::-webkit-slider-thumb { width: 10px; height: 10px; margin-top: -3.5px; }
  }
</style>
