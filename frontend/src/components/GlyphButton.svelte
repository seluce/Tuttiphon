<!-- Button with the current icon – opens the picker. <GlyphButton bind:value={welt.icon} onpick={changed} /> -->
<script>
  import Glyph from './Glyph.svelte'
  import GlyphPicker from './GlyphPicker.svelte'
  import { modal, closeModal } from '../lib/overlay.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  let { value = $bindable(''), onpick, size = 26 } = $props()

  async function choose() {
    let chosen = null
    const res = await modal({
      title: t('Choose icon'),
      component: GlyphPicker,
      props: { value, onpick: (v) => { chosen = v; closeModal('ok') } },
      buttons: [{ label: t('Cancel'), value: 'cancel' }],
    })
    if (res === 'ok' && chosen) {
      value = chosen
      onpick?.(chosen)
    }
  }
</script>

<button type="button" title={t('Change icon')} aria-label={t('Change icon')} onclick={choose}
  class="grid place-items-center shrink-0 w-12 h-12 rounded-[14px] bg-surface-2 border border-line-2 text-accent hover:border-accent transition-colors">
  <Glyph value={value || 'music'} {size} />
</button>
