<!-- "The idea in one sentence": music world × vibe × person (or taste) = playlist. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import { t } from '../../lib/i18n.svelte.js'

  let { admin } = $props()

  const cards = $derived(admin
    ? [['globe', t('Music world'), t('Who’s playing?'), t('Kids’ rock, medieval, rock …')], ['sliders', t('Vibe'), t('What’s on?'), t('Party, calm, Christmas, 80s …')], ['user', t('Person'), t('Who is it for?'), t('Family, Alex, Mia …')]]
    : [['globe', t('Music world'), t('Which music?'), t('Kids’ songs, medieval, rock …')], ['sliders', t('Vibe'), t('Which mood?'), t('Party, calm, Christmas …')], ['heart', t('Your taste'), t('What do you like?'), t('Favorite bands, dislikes')]])
</script>

{#snippet op(sign)}<div class="text-[1.4rem] font-extrabold text-muted max-mobile:hidden">{sign}</div>{/snippet}

<div class="flex flex-wrap items-center gap-2.5 mt-1.5">
  {#each cards as [ic, title, question, examples], i (title)}
    {#if i}{@render op('×')}{/if}
    <div class="card flex-[1_1_140px] grid gap-0.5 text-center p-3.5 bg-surface-2">
      <div class="grid place-items-center text-accent"><Icon name={ic} size={30} /></div>
      <b>{title}</b>
      <div>{question}</div>
      <div class="tiny muted">{examples}</div>
    </div>
  {/each}
  {@render op('=')}
  <div class="card flex-[1_1_140px] grid gap-0.5 text-center p-3.5 bg-[image:var(--grad)] text-white">
    <div class="grid place-items-center"><Icon name="playlists" size={30} /></div>
    <b>{t('Playlist')}</b>
    <div>{admin ? t('“Family · Kids’ rock · Party”') : t('“Kids’ rock · Party”')}</div>
    <div class="tiny">{t('keeps itself up to date')}</div>
  </div>
</div>
