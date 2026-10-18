<!-- "Getting started": ticks itself off live as soon as something is done. Administrator and user have their own lists. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import { S, isAdmin, ownPersons } from '../../lib/state.svelte.js'
  import { t } from '../../lib/i18n.svelte.js'

  const admin = isAdmin()
  /** [done, text, link, still missing (administrator only: accounts without a password)] */
  const items = $derived.by(() => {
    const cfg = S.config
    const mine = ownPersons().map((x) => x.id)
    const active = cfg.playlists.filter((x) => (x.status || 'aktiv') === 'aktiv' && (admin || mine.includes(x.person)))
    const users = S.status?.env?.users || []
    return admin ? [
      [users.length > 0 && users.every((u) => u.ok), t('Enter the passwords of all Navidrome accounts'), '#/einstellungen/navidrome', users.filter((u) => !u.ok).map((u) => u.name).join(', ')],
      [cfg.personen.some((x) => x.likes?.welten?.length || x.likes?.artists?.length), t('Set preferences for at least one person'), '#/personen'],
      [active.length > 0, t('Create your first playlist'), '#/neu'],  // i18n-ignore: route
      [active.some((x) => x.type === 'mix'), t('Try a mix'), '#/neu?type=mix'],  // i18n-ignore: route
      [active.some((x) => x.cover), t('Give a playlist a cover'), '#/playlists'],
      [Boolean(S.status?.deezer?.lastRun), t('Get Deezer stars: Home → Update everything'), '#/'],
      [Boolean(S.status?.env?.auth), t('Set up separate sign-ins for the family'), '#/hilfe/konten'],
    ] : [
      [mine.length > 0, t('Create your profile'), '#/willkommen'],
      [ownPersons().some((x) => x.likes?.welten?.length || x.likes?.artists?.length), t('Choose favorite worlds or bands'), '#/profil'],
      [active.length > 0, t('Create your first playlist'), '#/entdecken'],
      [active.some((x) => x.type === 'mix'), t('Try a mix'), '#/neu?type=mix'],  // i18n-ignore: route
      [Boolean(S.me?.passwordStored), t('Turn on statistics'), '#/einstellungen/konto'],
    ]
  })
  const done = $derived(items.filter((x) => x[0]).length)
</script>

<div class="card">
  <div class="card-head">
    <h2><span class="hi"><Icon name="check-circle" size={18} /></span>{t('Getting started')}</h2>
    <span class="pill" class:ok={done === items.length}>{t('{done} of {total}', { done, total: items.length })}</span>
  </div>
  <div class="progress h-1.5"><i style="width:{(done / items.length) * 100}%"></i></div>
  <div class="grid gap-1 mt-3">
    {#each items as [ok, label, href, extra] (label)}
      <a class="grid grid-cols-[24px_minmax(0,1fr)_auto] gap-2.5 items-center px-2.5 py-[9px] rounded-[10px] no-underline hover:bg-surface-2
        {ok ? 'text-muted' : 'text-text'}" {href}>
        <span class="grid place-items-center size-[22px] rounded-full border-2 {ok ? 'bg-ok border-transparent text-white' : 'border-line-2'}">
          {#if ok}<Icon name="check" size={14} />{/if}
        </span>
        <span class={ok ? 'line-through' : ''}>{label}{#if extra && !ok}<span class="muted small">{t(' – missing: {names}', { names: extra })}</span>{/if}</span>
        {#if !ok}<Icon name="right" size={16} />{/if}
      </a>
    {/each}
  </div>
</div>
