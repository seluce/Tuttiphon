<!--
  Collapsible help topic (anchor #h-<id>, data-topic for the search). flash: highlight briefly when arriving via
  #/hilfe/<id>. guides: matching "show me" guides, as buttons below the text.
-->
<script>
  import Icon from '../../components/Icon.svelte'
  import { startGuide } from '../../lib/tour.svelte.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { id, icon = '', title, open = false, hidden = false, flash = false, guides = [], ontoggle = undefined, children } = $props()
</script>

<details id="h-{id}" data-topic={id} class="fold scroll-mt-[84px] transition-shadow duration-400 {flash ? 'shadow-[0_0_0_3px_var(--accent)]' : ''}"
  {open} {hidden} {ontoggle}>
  <summary>{#if icon}<span class="hi"><Icon name={icon} size={18} /></span>{/if}{title}</summary>
  <div class="in [&_p]:leading-[1.6] [&_li]:leading-[1.6]">
    {@render children()}
    {#if guides.length}
      <div class="btns">
        {#each guides as g (g.id)}
          <button class="btn sm wrap" onclick={() => startGuide(g.id)}><Icon name="play" size={15} />{t('Show me: {title}', { title: g.title })}</button>
        {/each}
      </div>
    {/if}
  </div>
</details>
