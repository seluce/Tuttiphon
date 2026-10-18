<!-- Suggestion as a card ("You might like this"): image, title, reason, "Create" and ✕. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Mosaic from '../../components/Mosaic.svelte'
  import { findPerson, mixWording } from '../../lib/state.svelte.js'
  import { plEmoji } from '../../lib/playlist.js'
  import { plural } from '../../lib/format.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { s, multi = false, onaccept, ondismiss } = $props()
  const p = $derived(s.playlist)
  const mix = $derived(p.type === 'mix')
</script>

<div class="scard">
  <div class="relative min-w-0">
    <Mosaic covers={s.covers} marks={plEmoji(p)} />
    {#if mix}<span class="badge-mix">{t('Mix')}</span>{/if}
  </div>
  <div class="min-w-0">
    {#if s.because}<span class="pill acc tiny mb-1"><Icon name="sparkles" size={12} />{s.because}</span>{/if}
    <div class="t">{s.title}</div>
    <div class="w">{s.why}</div>
    <div class="tiny muted mt-1">
      {(multi ? `${t('for {name}', { name: findPerson(p.person)?.name || '?' })} · ` : '') + (mix ? `${mixWording(p)[1]}, ${plural(p.mix?.size || 50, 'song', 'songs')}` : plural(s.count, 'song', 'songs'))}
    </div>
    <div class="acts">
      <button class="btn primary sm" onclick={onaccept}><Icon name="plus" size={16} />{t('Create')}</button>
      <button class="btn icon sm ghost x" title={t('Not interested')} aria-label={t('Not interested')} onclick={ondismiss}><Icon name="x" size={16} /></button>
    </div>
  </div>
</div>
