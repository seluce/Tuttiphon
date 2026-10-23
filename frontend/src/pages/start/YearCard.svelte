<!--
  In December and January: the year in music is there – a card with listening time and band of the year that opens
  the story (#/jahr). Only when something was counted for the person this year.
-->
<script module>
  const seen = new Map()   // "<person>|<year>" -> the year's recap (or null) – once per visit
</script>

<script>
  import Icon from '../../components/Icon.svelte'
  import Avatar from '../../components/Avatar.svelte'
  import { api } from '../../lib/api.js'
  import { fmt } from '../../lib/format.js'
  import { recapYear, recapSeason, yearTitle } from '../jahr/year.js'
  import { t, tword } from '../../lib/i18n.svelte.js'

  let { person } = $props()
  const year = recapYear()
  const key = $derived(`${person?.id}|${year}`)
  let d = $state(null)
  $effect(() => {
    const k = key
    if (!recapSeason() || !person?.id) return
    if (seen.has(k)) { d = seen.get(k); return }
    api(`/api/rueckblick?kind=jahr&person=${encodeURIComponent(person.id)}&year=${year}`)
      .then((r) => { seen.set(k, r); if (k === key) d = r })
      .catch(() => seen.set(k, null))
  })
  const top = $derived(d?.topArtists?.[0])
  const hours = $derived(Math.round(d?.totals?.hours || 0))
</script>

{#if d?.totals?.plays}
  <a class="year" href="#/jahr/{person.id}/{year}">
    {#if top}<Avatar name={top.name} id={top.id} size={64} />{/if}
    <div class="flex-1 min-w-0">
      <div class="eyebrow">{t('The year in music')}</div>
      <b>{yearTitle(person, year)}</b>
      <div class="small ell">{tword(hours, '{n} hour of music', '{n} hours of music').replace('{n}', fmt(hours))}{#if top}{' · '}{t('Band of the year: {name}', { name: top.name })}{/if}</div>
    </div>
    <span class="btn white sm shrink-0"><Icon name="play" size={15} />{t('Look back')}</span>
  </a>
{/if}

<style>
  .year {
    display: flex; gap: 16px; align-items: center; padding: 16px 18px; margin-bottom: 22px; border-radius: var(--radius-card);
    background: var(--grad); color: #fff; box-shadow: 0 10px 30px rgba(217, 70, 239, .25);
  }
  .year .eyebrow { color: rgba(255, 255, 255, .8); }
  .year b { display: block; font-size: 1.25rem; font-weight: 850; }
  .year .small { color: rgba(255, 255, 255, .88); }
  @media (max-width: 520px) { .year .btn { display: none; } }
</style>
