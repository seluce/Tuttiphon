<!-- Bands similar to your favorites that are not in the library yet (Last.fm). -->
<script>
  import Icon from '../../components/Icon.svelte'
  import { isAdmin, defaultOwner } from '../../lib/state.svelte.js'
  import { api } from '../../lib/api.js'
  import { t } from '../../lib/i18n.svelte.js'

  const admin = isAdmin()
  const FIRST = 6   // this many first, the rest on request
  let d = $state.raw(null)
  let all = $state(false)
  const owner = defaultOwner()?.id   // your own person (administrators without one: the family's)
  api(`/api/missing${owner ? `?person=${encodeURIComponent(owner)}` : ''}`).then((r) => (d = r)).catch(() => {})
</script>

{#if d && !d.lastfm}
  <!-- as before: a card that looks like a note -->
  <div class="card note px-3.5 py-3 rounded-small bg-surface-2">
    {t('With a free Last.fm key, Tuttiphon shows bands here that resemble your favorites but are not in the library yet.')}
    {#if admin}<a class="link" href="#/einstellungen/intel">{t('Enter key →')}</a>{:else}{t('The administrator sets this up.')}{/if}
  </div>
{:else if d && !d.missing.length}
  <p class="muted small">{t('No data yet – it is created during the next run of “Understand music”.')}</p>
{:else if d}
  <div class="grid grid-cols-[repeat(auto-fill,minmax(230px,1fr))] gap-2.5">
    {#each all ? d.missing : d.missing.slice(0, FIRST) as m}
      <a class="grid grid-cols-[32px_minmax(0,1fr)_auto] gap-2.5 items-center px-3 py-2.5 rounded-card bg-surface border border-line no-underline hover:border-line-2"
        href="https://www.last.fm/music/{encodeURIComponent(m.artist)}" target="_blank" rel="noopener">
        <div class="hi"><Icon name="music" size={18} /></div>
        <div class="min-w-0"><b class="ell block">{m.artist}</b><div class="tiny muted ell">{t('similar to {names}', { names: m.because.join(', ') })}</div></div>
        <Icon name="external" size={14} />
      </a>
    {/each}
  </div>
  {#if !all && d.missing.length > FIRST}
    <button type="button" class="btn sm ghost mt-2" onclick={() => (all = true)}><Icon name="down" size={16} />{t('Show all {n}', { n: d.missing.length })}</button>
  {/if}
  <p class="hint mt-2">{admin
    ? t('According to Last.fm – to listen in or as a wish list for Lidarr.')
    : t('According to Last.fm – tap to listen in. If you like something, the administrator can add it to the library.')}</p>
{/if}
