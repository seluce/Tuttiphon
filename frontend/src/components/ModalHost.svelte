<!-- Draws the open dialog (lib/overlay.svelte.js → modal, confirmDialog). Enter triggers the default button. -->
<script>
  import Icon from './Icon.svelte'
  import { O, closeModal } from '../lib/overlay.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  const show = (dlg) => { if (!dlg.open) dlg.showModal() }
  const primary = $derived(O.modal?.buttons?.find((b) => b.primary))
</script>

<!-- {#each} instead of {#if}: when closing, m stays valid until the dialog is torn down -->
{#each O.modal ? [O.modal] : [] as m (m)}
  <dialog {@attach show} class="modal" class:wide={m.wide} aria-label={m.title}
    oncancel={(e) => { e.preventDefault(); closeModal('cancel') }}>
    <form class="flex flex-col max-h-[88vh]" onsubmit={(e) => { e.preventDefault(); if (primary) closeModal(primary.value) }}>
      <div class="flex justify-between items-center gap-2.5 px-[22px] pt-[18px] pb-2">
        <h2>{m.title}</h2>
        <button type="button" class="btn icon ghost shrink-0" aria-label={t('Close')} onclick={() => closeModal('cancel')}><Icon name="x" /></button>
      </div>
      <div class="px-[22px] pt-1.5 pb-[18px] overflow-auto grid gap-3.5">
        {#if m.text}<p class="muted">{m.text}</p>{/if}
        {#if m.component}<m.component {...m.props} />{:else}{@render m.body?.()}{/if}
      </div>
      {#if m.buttons?.length}
        <div class="flex gap-2.5 justify-end px-[22px] py-3.5 border-t border-line flex-wrap">
          {#each m.buttons as b (b.value)}
            {#if b === primary}
              <button type="submit" class="btn primary" class:danger={b.danger}>{b.label}</button>
            {:else}
              <button type="button" class="btn" class:danger={b.danger} onclick={() => closeModal(b.value)}>{b.label}</button>
            {/if}
          {/each}
        </div>
      {/if}
    </form>
  </dialog>
{/each}

<style>
  dialog.modal { border: 0; padding: 0; border-radius: var(--radius-big); background: var(--surface); color: var(--text); width: min(680px, calc(100vw - 28px)); max-width: none; max-height: none; margin: auto; box-shadow: 0 30px 80px rgba(0, 0, 0, .5); animation: fade .2s; }
  dialog.modal.wide { width: min(900px, calc(100vw - 28px)); }
  dialog.modal::backdrop { background: rgba(5, 5, 12, .6); backdrop-filter: blur(3px); }
</style>
