<!--
  Statistics: what is really being played? "Overall" from Navidrome's play counters, "This week", "30 days"
  and "Year" as a recap from the counters saved every day. Top right: the person (if there are several).
-->
<script module>
  // The chosen person stays when switching between the periods
  let current = null
</script>

<script>
  import Icon from '../components/Icon.svelte'
  import Glyph from '../components/Glyph.svelte'
  import PageHead from '../components/PageHead.svelte'
  import Empty from '../components/Empty.svelte'
  import Loading from '../components/Loading.svelte'
  import { showChosen } from '../components/Seg.svelte'
  import Overall from './stats/Overall.svelte'
  import Rueckblick from './stats/Rueckblick.svelte'
  import { S, isAdmin, ownPersons, defaultPerson, findPerson } from '../lib/state.svelte.js'
  import { api } from '../lib/api.js'
  import { passwordModal } from '../lib/account.js'
  import { t } from '../lib/i18n.svelte.js'

  let { kind: wanted = 'gesamt' } = $props()

  // [kind, text, short text for the phone]
  const year = new Date().getFullYear()
  const KINDS = $derived([['gesamt', t('Overall'), t('Overall')], ['woche', t('This week'), t('Week')], ['monat', t('30 days'), t('30 days')],
    ['jahr', t('Year {year}', { year }), String(year)]])
  const kind = $derived(KINDS.some(([k]) => k === wanted) ? wanted : 'gesamt')
  const admin = isAdmin()

  if (!current || !ownPersons().some((p) => p.id === current)) current = defaultPerson()   // person may have been deleted or belong to someone else
  let personId = $state(current)
  const persons = $derived(ownPersons())
  const person = $derived(findPerson(personId))
  const pwOk = (p) => (S.status?.env?.users || []).find((u) => u.name.toLowerCase() === (p.user || '').toLowerCase())?.ok

  let result = $state(null)   // { d } | { error } | null (loading)
  let seq = 0
  async function load() {
    const mine = ++seq   // only show the answer for the most recently chosen person
    result = null
    try {
      const d = await api(kind === 'gesamt' ? `/api/stats?person=${encodeURIComponent(personId)}`
        : `/api/rueckblick?kind=${kind}&person=${encodeURIComponent(personId)}`)
      if (mine === seq) result = { d }
    } catch (e) {
      if (mine === seq) result = { error: e.message }
    }
  }
  load()

  function choose(id) {
    current = personId = id
    load()
  }
  async function enterPassword() {
    if (await passwordModal(person.user)) load()
  }
</script>

<div class="page">
  <PageHead title={admin ? t('Statistics') : t('My statistics')} sub={admin
    ? t('What really gets played in your home – from the plays Symfonium reports to Navidrome.')
    : t('What you really listen to – from the plays Symfonium reports to Navidrome.')}>
    {#snippet actions()}
      {#if persons.length > 1}
        <div class="seg" {@attach showChosen(personId)}>
          {#each persons as p (p.id)}
            <button class:on={personId === p.id} onclick={() => choose(p.id)}>
              <Glyph value={p.icon} size={16} />{p.name}
              {#if !pwOk(p)}<span class="inline-flex opacity-70" title={t('Password missing')}><Icon name="lock" size={13} /></span>{/if}
            </button>
          {/each}
        </div>
      {/if}
    {/snippet}
  </PageHead>

  <div class="seg -mt-2 mb-5" {@attach showChosen(kind)}>
    {#each KINDS as [k, label, short] (k)}
      <a class:on={k === kind} href="#/statistik{k === 'gesamt' ? '' : '/' + k}"><span class="max-mobile:hidden">{label}</span><span class="hidden max-mobile:inline">{short}</span></a>
    {/each}
  </div>

  {#if !result}
    <Loading text={t('Counting your plays …')} />
  {:else if result.error}
    <Empty icon="lock" title={person?.name ? t('No statistics for {name}', { name: person.name }) : t('No statistics for this person')} text={result.error}>
      {#if !/kein Passwort|no password/i.test(result.error)}
        <!-- e.g. Navidrome currently unreachable: no password button (the regex matches the server's error text) -->
      {:else if !admin}
        <a class="btn primary" href="#/einstellungen/konto"><Icon name="key" size={16} />{t('Turn on statistics')}</a>
      {:else if person?.user}
        <button class="btn primary" onclick={enterPassword}>{t('Enter password')}</button>
      {/if}
    </Empty>
  {:else if kind === 'gesamt'}
    <Overall d={result.d} {person} />
  {:else}
    <Rueckblick d={result.d} {kind} />
  {/if}
</div>
