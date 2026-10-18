<!--
  Entry of a switchable list (sections of the home page, lyrics providers, steps of “Update everything”):
  switch, icon or rank, title with explanation, own buttons on the right (content).
-->
<script>
  import Icon from '../../components/Icon.svelte'
  import Switch from '../../components/Switch.svelte'

  let { on, onswitch, icon = '', rank = null, label, desc = '', children = undefined } = $props()
</script>

<!-- too narrow for the text (phone): the own buttons move to a line of their own, on the right -->
<div class={['flex flex-wrap gap-x-3 gap-y-1.5 items-center px-3 py-2.5 rounded-xl bg-surface-2 transition-opacity duration-200', !on && 'opacity-55']}>
  <Switch checked={on} onchange={onswitch} label={label} hidelabel />
  {#if icon}
    <span class="grid place-items-center size-[34px] shrink-0 rounded-[10px] bg-surface text-accent"><Icon name={icon} size={18} /></span>
  {/if}
  {#if rank != null}<span class="rank text-center font-extrabold">{rank}</span>{/if}
  <div class="min-w-0 flex-[1_1_9rem]">
    <b>{label}</b>
    <div class="hint">{desc}</div>
  </div>
  {#if children}<div class="flex gap-1 items-center ml-auto shrink-0">{@render children()}</div>{/if}
</div>
