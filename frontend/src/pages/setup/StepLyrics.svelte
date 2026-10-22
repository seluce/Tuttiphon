<!-- Setup step 3: lyrics – search and save as files next to the music, plain text too, providers, tidying up.
     Changes only the draft d. -->
<script>
  import Switch from '../../components/Switch.svelte'
  import Card from '../settings/Card.svelte'
  import Row from '../settings/Row.svelte'
  import { toast } from '../../lib/overlay.svelte.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { d } = $props()
  const ly = $derived(d.lyrics)

  const PROVIDERS = $derived({
    lrclib: ['LRCLIB', t('Open, free lyrics database – fast, synced lyrics and plain text.')],
    netease: ['NetEase', t('Large music platform with many synced lyrics, also for Western music. Unofficial interface, somewhat slower.')],
  })

  // the last provider cannot be turned off: redraw so the switch shows on again
  let key = $state(0)
  function setProvider(pv, on) {
    if (!on && !ly.providers.some((x) => x !== pv && x.on)) {
      toast(t('At least one provider must stay on.'), { error: true })
      key++
      return
    }
    pv.on = on
  }
</script>

<Card title={t('Lyrics')} icon="mic">
  <p class="muted small">{t('Tuttiphon looks up missing lyrics and saves them as files next to the songs: synced lyrics as .lrc, plain text as .txt. Navidrome reads them at the next scan, and many players show them – Symfonium even line by line while the song plays.')}</p>
  <Row label={t('Search for missing lyrics')} hint={t('Only adds files next to the songs – the music files stay untouched.')}>
    <Switch label={t('Search for missing lyrics')} hidelabel checked={ly.fetch} onchange={(v) => (ly.fetch = v)} />
  </Row>
  {#if ly.fetch}
    <Row label={t('Also save “text only”')} hint={t('If there are no synced ones.')}>
      <Switch label={t('Also save “text only”')} hidelabel checked={ly.savePlain} onchange={(v) => (ly.savePlain = v)} />
    </Row>
    {#key key}
      {#each ly.providers as pv (pv.id)}
        {@const [name, desc] = PROVIDERS[pv.id] || [pv.id, '']}
        <Row label={name} hint={desc}><Switch label={name} hidelabel checked={pv.on} onchange={(v) => setProvider(pv, v)} /></Row>
      {/each}
    {/key}
    <Row label={t('Replace “text only” with synced later')} hint={t('Regularly looks for a synced version for songs with .txt.')}>
      <Switch label={t('Replace “text only” with synced later')} hidelabel checked={ly.upgradePlain} onchange={(v) => (ly.upgradePlain = v)} />
    </Row>
  {/if}
  <Row label={t('Delete duplicate lyrics')} hint={t('If there is an .lrc next to a .txt, the .txt goes – otherwise Symfonium sometimes shows the wrong lyrics.')}>
    <Switch label={t('Delete duplicate lyrics')} hidelabel checked={ly.cleanup} onchange={(v) => (ly.cleanup = v)} />
  </Row>
</Card>
