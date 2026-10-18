<!-- Empty state: large icon, title, text and (as content) buttons. -->
<script>
  import Glyph from './Glyph.svelte'

  let { icon = 'info', title, text = '', class: cls = '', children = undefined } = $props()
</script>

<div class="empty {cls}">
  <div class="big"><Glyph value={icon} size={40} /></div>
  <b>{title}</b>
  {#if text}<div>{text}</div>{/if}
  {@render children?.()}
</div>
