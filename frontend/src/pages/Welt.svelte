<!--
  One music world: bands, scene and fine-tuning (administrators), or view, like and make a playlist
  from it (users). The data comes from /api/welt and is fetched again after every save.
-->
<script>
  import { untrack } from 'svelte'
  import Empty from '../components/Empty.svelte'
  import Loading from '../components/Loading.svelte'
  import WeltEdit from './welten/WeltEdit.svelte'
  import WeltView from './welten/WeltView.svelte'
  import { S, findWelt, isAdmin, save } from '../lib/state.svelte.js'
  import { api } from '../lib/api.js'
  import { debounce } from '../lib/format.js'
  import { t } from '../lib/i18n.svelte.js'

  let { id } = $props()

  const admin = isAdmin()
  // derived: after “Undo”, S.config is a new object
  const w = $derived(findWelt(id))
  let d = $state.raw(null)
  let error = $state(null)
  /** Counts reloads – editing (e.g. “Add band”) starts over afterwards */
  let loads = $state(0)

  async function reload() {
    try {
      await save()   // save first – otherwise the server does not know a world that was just created
      d = await api(`/api/welt?id=${encodeURIComponent(id)}`)
      error = null
      loads++
    } catch (e) {
      error = e.message
    }
  }
  const soon = debounce(reload, 700)
  untrack(() => { if (findWelt(id)) reload() })

  // reload after every save (the server computes bands, numbers and suggestions)
  let seen = S.saved
  $effect(() => {
    if (S.saved !== seen) {
      seen = S.saved
      soon()
    }
  })
</script>

{#if !w}
  <div class="page">
    <Empty icon="globe" title={t('This music world doesn’t exist')}><a class="btn" href="#/welten">{t('Go to music worlds')}</a></Empty>
  </div>
{:else}
  <div class="page">
    {#if error}
      <Empty icon="alert" title={t('Error')} text={error} />
    {:else if !d}
      <Loading />
    {:else if admin}
      {#key w}<WeltEdit {w} {d} {loads} />{/key}
    {:else}
      <WeltView {w} {d} />
    {/if}
  </div>
{/if}
