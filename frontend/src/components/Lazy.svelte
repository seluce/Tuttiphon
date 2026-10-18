<!-- A page that is loaded only when it is opened (own file in the build) – for large pages such as the help.
     Loaded once, it appears right away the next time. If the file cannot be loaded (usually: Tuttiphon was
     updated while the page was open and the old file is gone), a reload brings the new version. -->
<script module>
  /** load function → loaded module */
  const loaded = new Map()

  let background = 0
  /** Load a page in advance (in the background) – opening it later shows it at once. */
  export function preload(load) {
    if (loaded.has(load)) return
    background++
    load().then((m) => loaded.set(load, m)).catch(() => {}).finally(() => background--)
  }
  /** Is a page being loaded in the background right now? (Its failure must not reload the page – main.js.) */
  export const preloading = () => background > 0
</script>

<script>
  import Loading from './Loading.svelte'
  import Empty from './Empty.svelte'
  import Icon from './Icon.svelte'
  import { save } from '../lib/state.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  let { load, props = {} } = $props()

  const get = () => load().then((m) => { loaded.set(load, m); return m })
  const reload = () => save().finally(() => location.reload())
</script>

<!-- not a promise (already loaded): {#await} shows the page at once, without the loading indicator in between -->
{#await loaded.get(load) ?? get()}
  <Loading />
{:then m}
  <m.default {...props} />
{:catch}
  <Empty icon="alert" title={t('This page could not be loaded')} text={t('Tuttiphon has probably been updated in the meantime. Reload the page to get the new version.')}>
    <button class="btn primary" onclick={reload}><Icon name="refresh" size={16} />{t('Reload')}</button>
  </Empty>
{/await}
