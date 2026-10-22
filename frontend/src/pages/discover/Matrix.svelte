<!-- Table music world × vibe with song counts. Every cell is a possible playlist; colored = already exists. -->
<script>
  import Glyph from '../../components/Glyph.svelte'
  import Empty from '../../components/Empty.svelte'
  import Loading from '../../components/Loading.svelte'
  import { S, defaultOwner, weltIds, isAdmin, myPerson } from '../../lib/state.svelte.js'
  import { api } from '../../lib/api.js'
  import { go } from '../../lib/router.svelte.js'
  import { openEditor } from '../../lib/editor.js'
  import { fmt, plural } from '../../lib/format.js'
  import { GROUP_LABEL } from '../../lib/richtungen.js'
  import { t } from '../../lib/i18n.svelte.js'

  let m = $state.raw(null)
  let error = $state(null)
  api('/api/matrix').then((r) => (m = r)).catch((e) => (error = e.message))

  const cfg = $derived(S.config)
  const welten = $derived([{ id: '*', name: cfg.settings.allName || t('All'), icon: 'globe' }, ...cfg.welten])
  const max = $derived(m ? Math.max(1, ...Object.values(m.counts)) : 1)
  const groups = $derived([...new Set(['Genre', 'Thema', 'Jahreszeit', 'Zeitreise', 'Spezial', ...cfg.stile.map((s) => s.group)])]
    .map((g) => [g, cfg.stile.filter((s) => s.group === g)]).filter(([, st]) => st.length))
  // Does this combination already exist as a (simple) playlist?
  const exists = (w, s) => cfg.playlists.some((p) => p.status !== 'papierkorb' && !p.rules && !p.hits
    && weltIds(p).join() === (w === '*' ? '' : w) && (p.stil || '*') === s)

  function open(w, s) {
    if (!isAdmin() && !myPerson()) { go('#/willkommen'); return }   // an own profile first
    openEditor({ person: defaultOwner()?.id, welt: w === '*' ? '*' : w, stil: s, source: 'tabelle' },
      { isNew: true, onSaved: (p) => go(`#/playlist/${encodeURIComponent(p.id)}`) })
  }
</script>

{#snippet cell(w, s)}
  {@const n = m.counts[`${w}|${s}`] ?? 0}
  {@const on = exists(w, s)}
  <td>
    <button class="cell" class:active={on} class:zero={!on && !n} title={plural(n, 'song', 'songs')} onclick={() => n && open(w, s)}
      style:--heat="{n ? Math.round(8 + 62 * Math.log10(n + 1) / Math.log10(max + 1)) : 0}%">{n ? fmt(n) : '·'}</button>
  </td>
{/snippet}

{#if error}
  <Empty icon="alert" title={t('Error')} text={error} />
{:else if !m}
  <Loading text={t('Computing all combinations …')} />
{:else}
  <p class="muted small mb-2.5">{t('Every cell is a possible playlist. Colored = already exists. A click opens it for creating.')}</p>
  <div class="matrix-wrap">
    <table class="matrix">
      <thead>
        <tr>
          <th></th>
          {#each welten as w (w.id)}<th><span class="ico"><Glyph value={w.icon} size={16} /></span>{w.name}</th>{/each}
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>{t('Everything mixed')}</th>
          <td></td>
          {#each welten.slice(1) as w (w.id)}{@render cell(w.id, '*')}{/each}
        </tr>
        {#each groups as [g, st] (g)}
          <tr class="group"><th colspan={welten.length + 1}>{GROUP_LABEL[g] ?? g}</th></tr>
          {#each st as s (s.id)}
            <tr>
              <th>
                <Glyph value={s.icon} size={15} class="inline-flex align-[-3px] mr-1.5" />{s.name}
                {#if m.activeSeason.includes(s.id)}<span class="pill acc ml-1.5">{t('now')}</span>{/if}
              </th>
              {#each welten as w (w.id)}{@render cell(w.id, s.id)}{/each}
            </tr>
          {/each}
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .matrix { border-collapse: separate; border-spacing: 0; width: 100%; font-size: .88rem; }
  .matrix th, .matrix td { padding: 3px; }
  .matrix thead th { position: sticky; top: 0; z-index: 2; background: var(--surface); padding: 12px 6px 8px; text-align: center; vertical-align: bottom; min-width: 92px; font-weight: 700; }
  .matrix thead th .ico { display: flex; justify-content: center; align-items: center; height: 1.95rem; }
  .matrix tbody th { position: sticky; left: 0; z-index: 1; background: var(--surface); text-align: left; white-space: nowrap; padding: 3px 14px; font-weight: 600; }
  .matrix tr.group th { padding: 14px 14px 4px; font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
  .cell { width: 100%; min-width: 80px; height: 34px; border: 0; border-radius: 8px; cursor: pointer; font-weight: 650; font-variant-numeric: tabular-nums; color: var(--text); background: color-mix(in srgb, var(--accent) var(--heat, 0%), var(--surface-2)); }
  .cell:hover { outline: 2px solid var(--accent); outline-offset: -2px; }
  .cell.zero { background: none; color: var(--muted); opacity: .4; cursor: default; }
  .cell.zero:hover { outline: 0; }
  .cell.active { background: var(--grad); color: #fff; }
</style>
