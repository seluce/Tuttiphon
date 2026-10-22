<!-- Settings → Lyrics: status, providers & order, searching, cleanup, manual runs, lyrics search & kid-safe mode. -->
<script>
  import { untrack } from 'svelte'
  import Icon from '../../components/Icon.svelte'
  import Seg from '../../components/Seg.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import Toggle from './Toggle.svelte'
  import NumInput from './NumInput.svelte'
  import SecItem from './SecItem.svelte'
  import MoveButtons from './MoveButtons.svelte'
  import Kinderschutz from './Kinderschutz.svelte'
  import { S, changed, runTask } from '../../lib/state.svelte.js'
  import { go } from '../../lib/router.svelte.js'
  import { api } from '../../lib/api.js'
  import { fmt, serverDate } from '../../lib/format.js'
  import { t } from '../../lib/i18n.svelte.js'

  const PROVIDERS = $derived({
    lrclib: ['LRCLIB', t('Open, free lyrics database – fast, synced lyrics and plain text.')],
    netease: ['NetEase', t('Large music platform with many synced lyrics, also for Western music. Unofficial interface, somewhat slower.')],
  })

  S.config.settings.lyrics ??= {}
  const ly = S.config.settings.lyrics
  ly.providers ??= [{ id: 'lrclib', on: true }, { id: 'netease', on: false }]
  for (const id of untrack(() => Object.keys(PROVIDERS))) if (!ly.providers.some((x) => x.id === id)) ly.providers.push({ id, on: false })

  /** null = loading, false = no numbers (error) */
  let stats = $state.raw(null)
  api('/api/lyrics/stats').then((d) => { stats = d }).catch(() => { stats = false })

  const startTask = (steps, opts) => runTask(steps, opts).then((ok) => { if (ok) go('#/') })
</script>

{#snippet part(n, cls, label)}
  <i class={cls} style:width="{n / stats.total * 100}%" title="{label}: {fmt(n)}"></i>
{/snippet}

<Card title={t('Find lyrics automatically')} icon="mic">
  <p class="muted small">{t('Tuttiphon looks up missing lyrics on LRCLIB, and on NetEase too if you like, and puts them next to the songs: synced lyrics as .lrc, otherwise as .txt. Navidrome reads them in at the next scan, Symfonium shows them while playing.')}</p>
  <div>
    {#if stats === null}
      <div class="skel h-[70px]"></div>
    {:else if stats && !stats.total}
      <p class="muted small">{t('No numbers yet – they appear with the first run.')}</p>
    {:else if stats}
      <div class="stack-bar">
        {@render part(stats.synced, 'a', t('synced'))}
        {@render part(stats.plain, 'b', t('text only'))}
        {@render part(stats.missing, 'c', t('without lyrics'))}
      </div>
      <div class="legend">
        <span><i class="a"></i>{t('{n} synced', { n: fmt(stats.synced) })}</span>
        <span><i class="b"></i>{t('{n} text only', { n: fmt(stats.plain) })}</span>
        <span><i class="c"></i>{t('{n} without lyrics', { n: fmt(stats.missing) })}</span>
        {#if stats.lastRun}<span class="muted">{t('last run {when}', { when: serverDate(stats.lastRun) })}</span>{/if}
      </div>
    {/if}
  </div>
  <Row label={t('Search for missing lyrics')}><Toggle obj={ly} key="fetch" /></Row>
  <Row full label={t('Providers & order')} hint={t('Asked in order; synced lyrics win – if the first finds only plain text, Tuttiphon asks the next ones for a synced version.')}>
    <div class="grid gap-1.5">
      {#each ly.providers as pv, i (pv.id)}
        {@const [name, desc] = PROVIDERS[pv.id] || [pv.id, '']}
        <SecItem on={pv.on} onswitch={(v) => { pv.on = v; changed() }} rank={i + 1} label={name} {desc}>
          <MoveButtons list={ly.providers} {i} />
        </SecItem>
      {/each}
    </div>
  </Row>
  <Row label={t('Time limit for “Update everything”')} hint={t('Tuttiphon searches at most this long per run – the rest comes next time. New songs always go first. 0 = no limit.')}>
    <div class="btns"><NumInput obj={ly} key="budgetMinutes" min={0} max={600} placeholder="5" width={90} /><span class="muted small">{t('minutes')}</span></div>
  </Row>
  <Row label={t('Also save “text only”')} hint={t('If there are no synced ones.')}><Toggle obj={ly} key="savePlain" /></Row>
  <Row label={t('Replace “text only” with synced later')} hint={t('Regularly looks for a synced version for songs with .txt.')}><Toggle obj={ly} key="upgradePlain" /></Row>
  <Row label={t('Instrumental tracks')} hint={t('Mark as “instrumental” – then Tuttiphon doesn’t keep searching there.')}>
    <Seg options={[['mark', t('mark')], ['skip', t('save nothing')]]} value={ly.instrumental || 'mark'} onchange={(v) => { ly.instrumental = v; changed() }} />
  </Row>
  <Row label={t('Retry search')} hint={t('What wasn’t found is only searched again after this many days.')}>
    <div class="btns"><NumInput obj={ly} key="retryDays" min={1} max={365} placeholder="30" width={90} /><span class="muted small">{t('days later')}</span></div>
  </Row>
  <Row label={t('Simultaneous requests')} hint={t('LRCLIB is a community project – better go easy.')}>
    <NumInput obj={ly} key="workers" min={1} max={8} placeholder="6" width={90} />
  </Row>
</Card>

<Card title={t('Cleanup')} icon="eraser">
  <Row label={t('Delete duplicate lyrics')} hint={t('If there is an .lrc next to a .txt, the .txt goes – otherwise Symfonium sometimes shows the wrong lyrics.')}>
    <Toggle label={t('Delete duplicate lyrics')} obj={ly} key="cleanup" />
  </Row>
</Card>

<Card title={t('Run now')} icon="play">
  <div class="btns">
    <button class="btn primary sm" disabled={S.running} onclick={() => startTask(['lyrics'], { lyrics_full: true })}><Icon name="search" size={15} />{t('Search all missing now')}</button>
    <button class="btn sm" disabled={S.running} onclick={() => startTask(['lyrics'], { lyrics_all: true })}>{t('Retry recent misses too')}</button>
    <button class="btn sm ghost" disabled={S.running} onclick={() => startTask(['lyrics'], { dry_run: true })}>{t('Dry run')}</button>
  </div>
  <div class="hint">{t('“Search all missing now” runs without a time limit and can be stopped at any time. For the lyrics to appear in Navidrome, a scan is needed afterwards. With “Update everything” this happens automatically.')}</div>
</Card>

<Kinderschutz />

<style>
  .stack-bar { display: flex; height: 12px; border-radius: 99px; overflow: hidden; background: var(--surface-3); gap: 2px; }
  .stack-bar i { display: block; height: 100%; }
  .legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: .82rem; margin-top: 8px; }
  .legend span { display: inline-flex; gap: 6px; align-items: center; }
  .legend i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
  .a { background: var(--accent); }
  .b { background: color-mix(in srgb, var(--accent) 45%, var(--surface-3)); }
  .c { background: var(--surface-3); }
</style>
