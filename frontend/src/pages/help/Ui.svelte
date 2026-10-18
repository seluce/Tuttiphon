<!-- Interface button in the help text – looks like the original so it is recognizable: <Ui icon="dice">Reshuffle</Ui> -->
<script>
  import Icon from '../../components/Icon.svelte'

  let { icon = '', primary = false, children } = $props()
</script>

<span class="inline-flex items-center gap-1 align-[-2px] px-2 py-px rounded-full border text-[.84em] font-semibold whitespace-nowrap
  {primary ? 'bg-accent text-white border-transparent' : 'bg-surface-2 border-line-2 text-text'}">{#if icon}<Icon name={icon} size={13} />{/if}{@render children()}</span>
