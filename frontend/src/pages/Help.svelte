<!--
  Help & guide: search, "What would you like to do?" with "Show me" guides right in the interface
  (lib/guides.js), first steps (checked off live), guides to expand, questions & answers and terms.
  Administrators see everything, users a simpler help only about what they can do themselves.
  #/hilfe/<topic> expands the section, jumps to it and highlights it briefly. Content: pages/help/.
-->
<script>
  import { untrack } from 'svelte'
  import Icon from '../components/Icon.svelte'
  import PageHead from '../components/PageHead.svelte'
  import Section from '../components/Section.svelte'
  import Empty from '../components/Empty.svelte'
  import Topic from './help/Topic.svelte'
  import GuideCard from './help/GuideCard.svelte'
  import Idea from './help/Idea.svelte'
  import Checklist from './help/Checklist.svelte'
  import { ADMIN_TOPICS } from './help/AdminTopics.svelte'
  import { USER_TOPICS } from './help/UserTopics.svelte'
  import { ADMIN_FAQ, USER_FAQ, GLOSSAR } from './help/texts.js'
  import { guidesFor, guideById } from '../lib/guides.js'
  import { isAdmin } from '../lib/state.svelte.js'
  import { t, lang } from '../lib/i18n.svelte.js'

  let { topic = null } = $props()

  const admin = isAdmin()
  const guides = $derived(guidesFor(admin))
  const topics = $derived([{ id: 'idee', icon: 'sparkles', title: t('How Tuttiphon works'), body: idee }, ...(admin ? ADMIN_TOPICS : USER_TOPICS)])
  const guidesOf = (tp) => (tp.guides || []).map(guideById).filter((g) => guides.includes(g))
  const faq = $derived(admin ? ADMIN_FAQ : USER_FAQ)
  const glossar = $derived(GLOSSAR.filter(([, , tech]) => admin || !tech))

  // Intro below the page title, split around the help icon that sits in the sentence
  const intro = $derived((admin
    ? t('“Show me” walks you through the steps right on the page; below, everything is there to look up. The {icon} next to every page title explains that page.')
    : t('“Show me” walks you through the steps right on the page. The {icon} next to every page title explains that page.')).split('{icon}'))

  // Search: every word must occur – in the title, text or search words
  let query = $state('')
  const words = $derived(query.toLowerCase().split(/\s+/).filter(Boolean))
  const hit = (text) => words.every((w) => text.includes(w))
  /** Searchable text per guide – read from the page after rendering, since the contents are snippets */
  let texts = $state.raw({})
  // on opening and again after a language switch (effects run once the page shows the new texts)
  $effect(() => {
    lang()
    const found = {}
    for (const el of document.querySelectorAll('[data-topic]')) found[el.dataset.topic] = el.textContent.toLowerCase()
    texts = found
  })
  const guideHits = $derived(guides.filter((g) => hit(`${g.title} ${g.short.join(' ')} ${g.keys || ''}`.toLowerCase())))
  const topicHit = (tp) => hit(texts[tp.id] || tp.title.toLowerCase())
  const topicHits = $derived(topics.filter(topicHit).length)
  const faqHits = $derived(faq.filter(([q, a]) => hit(`${q} ${a}`.toLowerCase())))
  const glossHits = $derived(glossar.filter(([term, text]) => hit(`${term} ${text}`.toLowerCase())))
  const nothing = $derived(words.length > 0 && !guideHits.length && !topicHits && !faqHits.length && !glossHits.length)

  /** expanded guides – while searching, all hits are open */
  let open = $state({})
  /** section that is briefly highlighted right now (after jumping via #/hilfe/<topic>) */
  let flash = $state(null)
  // On opening and on every link to a topic (the page stays, only topic changes)
  $effect(() => {
    const id = topic
    if (!id) return
    untrack(() => { query = '' })   // otherwise the search would hide the topic
    open[id] = true
    let wait, off, gone = false
    const frame = requestAnimationFrame(() => {
      wait = setTimeout(async () => {
        const el = document.getElementById(`h-${id}`)
        if (!el) return
        // only once the page has finished fading in (.page slides a few pixels on opening) – otherwise the jump misses
        await Promise.all((el.closest('.page')?.getAnimations() ?? []).map((a) => a.finished.catch(() => {})))
        if (gone) return
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
        flash = id
        off = setTimeout(() => (flash = null), 1600)
      }, 60)
    })
    return () => { gone = true; cancelAnimationFrame(frame); clearTimeout(wait); clearTimeout(off) }
  })
</script>

{#snippet idee()}
  {#if admin}
    <p>{@html t('You say <b>who</b> should play and <b>what</b> kind of mood – from that, Tuttiphon builds playlists that keep themselves up to date: new albums are included automatically, stars from Deezer pick out the hits, and what you listen to in Symfonium makes the suggestions personal.')}</p>
  {:else}
    <p>{@html t('You say <b>what music</b> you like and <b>what you’re in the mood for</b> – from that, Tuttiphon builds playlists from your library that keep themselves up to date. Along the way it learns from what you listen to in Symfonium. You listen to everything in Symfonium as usual.')}</p>
  {/if}
  <Idea {admin} />
{/snippet}

<div class="page">
  <PageHead title={t('Help & guide')} eyebrow={t('Help')}>
    <p>{intro[0]}<Icon name="help" size={15} />{intro[1]}</p>
  </PageHead>

  <div class="search max-w-[560px] mb-2">
    <Icon name="search" size={18} />
    <input bind:value={query} placeholder={admin ? t('Search help') : t('What do you need help with?')}
      aria-label={t('Search help')} autocomplete="off" />
  </div>

  {#if guideHits.length}
    <Section title={words.length ? t('Hands-on guides') : t('What would you like to do?')} icon="sparkles">
      <div class="grid grid-cols-[repeat(auto-fill,minmax(min(100%,340px),1fr))] gap-3.5">
        {#each guideHits as g (g.id)}<GuideCard {g} />{/each}
      </div>
    </Section>
  {/if}

  {#if !words.length}
    <div class="section"><Checklist /></div>
  {/if}

  <Section title={t('Reference')} icon="list" class={topicHits ? '' : 'hidden'}>
    <div class="grid gap-2.5 items-start min-[1300px]:grid-cols-2">
      {#each topics as tp (tp.id)}
        <Topic id={tp.id} icon={tp.icon} title={tp.title} guides={guidesOf(tp)} flash={flash === tp.id}
          hidden={!topicHit(tp)} open={words.length > 0 || !!open[tp.id]}
          ontoggle={(e) => { if (!words.length) open[tp.id] = e.currentTarget.open }}>{@render tp.body()}</Topic>
      {/each}
    </div>
  </Section>

  {#if faqHits.length}
    <div id="h-fragen" class="scroll-mt-[84px] rounded-card transition-shadow duration-400 {flash === 'fragen' ? 'shadow-[0_0_0_3px_var(--accent)]' : ''}">
      <Section title={t('Questions & answers')} icon="help">
        <div class="card py-1.5">
          {#each faqHits as [q, a] (q)}
            <details class="border-b border-line last:border-b-0 py-1" open={words.length > 0}>
              <summary class="cursor-pointer py-2.5 font-[650]">{q}</summary>
              <p class="text-muted pb-3 leading-[1.6] max-w-[100ch]">{a}</p>
            </details>
          {/each}
        </div>
      </Section>
    </div>
  {/if}

  {#if glossHits.length}
    <div id="h-begriffe" class="scroll-mt-[84px] rounded-card transition-shadow duration-400 {flash === 'begriffe' ? 'shadow-[0_0_0_3px_var(--accent)]' : ''}">
      <Section title={t('Terms')} icon="text">
        <dl class="card grid grid-cols-[max-content_minmax(0,1fr)] gap-x-[18px] gap-y-2 m-0 max-mobile:grid-cols-1 max-mobile:gap-0.5">
          {#each glossHits as [term, text] (term)}
            <dt class="font-bold">{term}</dt>
            <dd class="text-muted m-0 leading-[1.6] max-w-[100ch] max-mobile:mb-2.5">{text}</dd>
          {/each}
        </dl>
      </Section>
    </div>
  {/if}

  {#if nothing}
    <Empty icon="search" title={t('Nothing found')} text={admin ? t('Try a different word.') : t('Try a different word or ask the administrator.')} />
  {/if}
</div>
