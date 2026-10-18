<!-- Setup step 5: star ratings from Deezer – on/off (step “deezer”), whose accounts, stars given by hand.
     Changes only the draft d. -->
<script>
  import Icon from '../../components/Icon.svelte'
  import Switch from '../../components/Switch.svelte'
  import Card from '../settings/Card.svelte'
  import Row from '../settings/Row.svelte'
  import Choice from './Choice.svelte'
  import { S } from '../../lib/state.svelte.js'
  import { t } from '../../lib/i18n.svelte.js'

  let { d } = $props()
  const dz = $derived(d.deezer)

  const users = $derived((S.status?.env?.users || []).map((u) => u.name))
  const chosen = $derived(dz.users ?? users)
  function toggleUser(u) {
    const cur = new Set(dz.users ?? users)
    if (cur.has(u)) cur.delete(u)
    else cur.add(u)
    dz.users = [...cur]
  }
</script>

<Card title={t('Star ratings from Deezer')} icon="star">
  <p class="muted small">{t('Deezer knows how popular almost every song is. Tuttiphon turns that into stars in Navidrome: apps like Symfonium then sort the top tracks of every band correctly, and the “Only the hits” playlists know which songs are the hits. No Deezer account needed.')}</p>
  <Row label={t('Set stars from Deezer')} hint={t('New songs are rated during “Update everything”; in the time window of the night analysis a portion is checked again every night.')}>
    <Switch checked={dz.on} onchange={(v) => (dz.on = v)} />
  </Row>
  {#if dz.on}
    <Row full label={t('Who gets stars?')} hint={t('In Navidrome, stars are per account. Accounts without a password are skipped.')}>
      {#if users.length}
        <div class="toggles">
          {#each users as u (u)}
            <button class={['toggle', chosen.includes(u) && 'on']} onclick={() => toggleUser(u)}>{u}</button>
          {/each}
        </div>
      {:else}
        <p class="muted small">{t('No accounts yet – create them under People first.')}</p>
      {/if}
    </Row>
    <Row full label={t('Songs rated by hand')}>
      <Choice name="setup-manual" value={dz.overwriteManual ? 'overwrite' : 'keep'} onchange={(v) => (dz.overwriteManual = v === 'overwrite')} options={[
        ['keep', t('Keep their stars'), t('Stars someone gave by hand stay – Deezer only rates the other songs.')],
        ['overwrite', t('Overwrite'), t('The Deezer rating replaces stars given by hand too.')],
      ]} />
    </Row>
    {#if dz.overwriteManual}
      <div class="note flex gap-2.5 items-start text-warn border border-warn/40">
        <Icon name="alert" size={18} class="shrink-0 mt-0.5" />
        <span>{t('Stars given by hand are lost with the next rating – they cannot be restored.')}</span>
      </div>
    {/if}
  {/if}
</Card>
