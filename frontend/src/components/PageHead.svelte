<!--
  Page header: title with help (?), subtitle, actions on the right.
  <PageHead title="Playlists" sub="…">{#snippet actions()}<a class="btn primary" …>{/snippet}</PageHead>
  children: additional content below the subtitle.
-->
<script>
  import HelpLink from './HelpLink.svelte'

  let { title, sub = '', eyebrow = '', help = undefined, actions = undefined, children = undefined } = $props()
</script>

<div class="page-head">
  <div>
    {#if eyebrow}<div class="eyebrow">{eyebrow}</div>{/if}
    <h1>{title}<HelpLink topic={help} /></h1>
    {#if sub}<p>{sub}</p>{/if}
    {@render children?.()}
  </div>
  {@render actions?.()}
</div>
