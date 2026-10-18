<!-- History of all runs with their log (administrators only). -->
<script>
  import { untrack } from 'svelte'
  import PageHead from '../components/PageHead.svelte'
  import HistoryRows from '../components/HistoryRows.svelte'
  import Empty from '../components/Empty.svelte'
  import Icon from '../components/Icon.svelte'
  import { S } from '../lib/state.svelte.js'
  import { api } from '../lib/api.js'
  import { t } from '../lib/i18n.svelte.js'

  let error = $state(null)
  const load = () => api('/api/history').then((d) => { S.history = d; error = null }).catch((e) => { error = e.message })
  // fetch fresh on opening and after every finished run
  $effect(() => { S.done; untrack(load) })
</script>

<div class="page">
  <PageHead title={t('History')} sub={t('Every run with its result – a click shows the complete log.')} />
  {#if error && !S.history.length}
    <!-- not "no runs yet": the list could not be loaded -->
    <Empty icon="alert" title={t('Could not be loaded')} text={error}>
      <button class="btn" onclick={load}><Icon name="refresh" size={16} />{t('Try again')}</button>
    </Empty>
  {:else}
    <HistoryRows list={S.history} />
  {/if}
</div>
