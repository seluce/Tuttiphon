<!-- Loading indicator within the page. data-loading: guides wait as long as it is visible (components/Tour.svelte). -->
<script>
  import Icon from './Icon.svelte'
  import { t } from '../lib/i18n.svelte.js'

  let { text } = $props()
</script>

<div class="empty border-0" data-loading>
  <div class="big"><Icon name="loader" size={34} class="animate-spin" /></div>
  <div>{text ?? t('Loading…')}</div>
</div>
