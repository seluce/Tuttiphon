<!-- Card under "What would you like to do?": three short steps, "show me" starts the guide in the interface,
     "jump right in" goes straight there. g: guide from lib/guides.js -->
<script>
  import Icon from '../../components/Icon.svelte'
  import { startGuide } from '../../lib/tour.svelte.js'
  import { go } from '../../lib/router.svelte.js'
  import { guideHref } from '../../lib/guides.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { g } = $props()

  function start() {
    if (g.focus) document.querySelector('[data-tour=search] input')?.focus()
    else go(guideHref(g))
  }
</script>

<div class="card grid gap-3 content-start p-[18px]">
  <div class="flex gap-3 items-center">
    <span class="hi size-10 rounded-xl"><Icon name={g.icon} size={20} /></span>
    <h3 class="text-[1.02rem] leading-tight">{g.title}</h3>
  </div>
  <ol class="grid gap-1.5 p-0 m-0 list-none text-[.9rem] text-text-2">
    {#each g.short as s, i (i)}
      <li class="flex gap-2.5 items-baseline">
        <span class="grid place-items-center shrink-0 size-5 rounded-full bg-surface-3 text-[.72rem] font-extrabold text-muted">{i + 1}</span>{s}
      </li>
    {/each}
  </ol>
  <div class="btns mt-1">
    <button class="btn primary sm" onclick={() => startGuide(g.id)}><Icon name="play" size={15} />{t('Show me')}</button>
    <button class="btn sm ghost" onclick={start}>{t('Jump right in')}<Icon name="right" size={15} /></button>
  </div>
</div>
