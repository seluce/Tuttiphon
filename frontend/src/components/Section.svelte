<!-- Section of a page: heading (optionally with icon), an action on the right (snippet), the content below. -->
<script>
  import Glyph from './Glyph.svelte'

  let { title, icon = '', action = undefined, class: cls = '', children } = $props()
</script>

<section class="section {cls}">
  <div class="section-head">
    <h2 class="ih">
      {#if icon}<span class="hi"><Glyph value={icon} size={18} /></span>{/if}
      {title}
    </h2>
    {@render action?.()}
  </div>
  {@render children?.()}
</section>
