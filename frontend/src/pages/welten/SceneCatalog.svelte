<!-- Content of the “New music world” dialog: scenes from the catalog as cards. onpick(scene) -->
<script>
  import Collage from '../../components/Collage.svelte'
  import { t, tn } from '../../lib/i18n.svelte.js'

  let { list = [], onpick } = $props()
</script>

<div class="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-3">
  {#each list as s (s.id)}
    <button type="button" class="wcard text-left p-0" onclick={() => onpick(s)}>
      <Collage artists={s.present.map((a, i) => [a, 0, s.presentIds[i]])} icon={s.icon} title={s.name}
        sub={s.present.length ? tn(s.present.length, '{n} band in your library', '{n} bands in your library') : t('no bands in your library yet')} />
      <div class="body"><div class="muted small">{s.description}</div></div>
    </button>
  {/each}
</div>
