<!-- Help sheet behind the (?) next to the page title: the matching "show me" guides on top, the page's explanation
     below. topic: topic from AdminTopics/UserTopics, guides: guides from lib/guides.js -->
<script>
  import Icon from '../../components/Icon.svelte'
  import { startGuide } from '../../lib/tour.svelte.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { topic, guides = [] } = $props()
</script>

{#if guides.length}
  <div class="grid gap-2">
    {#each guides as g (g.id)}
      <button class="flex gap-3 items-center w-full p-3 rounded-card border border-line bg-surface hover:bg-surface-2 text-left cursor-pointer text-text"
        onclick={() => startGuide(g.id)}>
        <span class="hi size-10 rounded-xl"><Icon name={g.icon} size={20} /></span>
        <span class="flex-1 min-w-0"><b class="block">{g.title}</b><span class="tiny muted">{t('Show me – step by step on the page')}</span></span>
        <span class="grid place-items-center size-9 rounded-full bg-accent text-white shrink-0"><Icon name="play" size={16} /></span>
      </button>
    {/each}
  </div>
{/if}
<div class="grid gap-3 [&_p]:leading-[1.6] [&_li]:leading-[1.6]">{@render topic.body()}</div>
<a class="btn justify-self-start" href="#/hilfe/{topic.id}"><Icon name="help" size={16} />{t('Open full help')}</a>
