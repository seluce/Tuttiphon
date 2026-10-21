<!-- Settings → Navidrome: connection (address, admin account), passwords of the accounts, type of scan, the Navidrome
     plugin (NavidromePlugin.svelte). -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Seg from '../../components/Seg.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import Connection from './Connection.svelte'
  import NavidromePlugin from './NavidromePlugin.svelte'
  import { S, changed } from '../../lib/state.svelte.js'
  import { passwordModal } from '../../lib/account.js'
  import { t } from '../../lib/i18n.svelte.js'

  const env = $derived(S.status?.env || {})

  S.config.settings.navidrome ??= {}
  const nav = S.config.settings.navidrome
</script>

<Card title={t('Connection')} icon="plug">
  <Connection />
</Card>

<Card title={t('Accounts & passwords')} icon="users" guide="passwoerter">
  {#each env.users || [] as u (u.name)}
    <!-- works = stored and not rejected by Navidrome the last time it was used (rejected: changed in Navidrome) -->
    {@const works = u.ok && !u.rejected}
    <div class="member-row">
      <Icon name={works ? 'check' : u.ok ? 'alert' : 'lock'} size={18} class={works ? 'ok-t' : 'warn-t'} />
      <div class="flex-1 min-w-0">
        <b>{u.name}</b>
        <div class="tiny muted">{works ? t('Password stored') : u.ok ? t('The stored password no longer works – probably it was changed in Navidrome.') : t('Password missing – stars, accurate preview and statistics won’t work then')}</div>
      </div>
      <button class={['btn sm', !works && 'primary']} onclick={() => passwordModal(u.name)}>{u.ok ? t('Change') : t('Enter')}</button>
    </div>
  {/each}
  <div class="hint">{@html t('The list comes from the Navidrome accounts of your <a class="link" href="#/personen">people</a>. Anyone who signs in and leaves the “Turn on statistics & stars” box checked enters it themselves. Roles: <a class="link" href="#/einstellungen/benutzer">Users & permissions</a>.')}</div>
</Card>

<Card title={t('Scan')} icon="refresh">
  <Row label={t('Type of scan')} hint={t('“Quick” reads in only what changed and takes seconds. “Full” checks every file – only needed if Navidrome missed something.')}>
    <Seg options={[['quick', t('Quick')], ['full', t('Full')]]} value={nav.scan || 'quick'} onchange={(v) => { nav.scan = v; changed() }} />
  </Row>
</Card>

<NavidromePlugin />
