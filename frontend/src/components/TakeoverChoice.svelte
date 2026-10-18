<!-- Content of the takeover dialog: unchanged or switch to the builder. Writes the choice to choice.mode. -->
<script>
  import { fmt } from '../lib/format.js'
  import { t } from '../lib/i18n.svelte.js'

  let { info, choice } = $props()
  let mode = $state('unveraendert')
  $effect(() => { choice.mode = mode })
</script>

<label class="choice">
  <input type="radio" name="tk" value="unveraendert" bind:group={mode} />
  <b>{t('Take over unchanged')}</b>
  <span>{t('{n} songs · the rules stay exactly as they are. You can change name, person, count and order afterwards.', { n: fmt(info.originalCount) })}</span>
</label>
{#if info.mapping}
  <label class="choice">
    <input type="radio" name="tk" value="baukasten" bind:group={mode} />
    <b>{t('Switch to the builder: {what}', { what: info.mapping.describe })}</b>
    <span>{t('{n} songs · with automatically detected bands, a more precise live filter and all the tool’s settings.', { n: fmt(info.mapping.count) })}</span>
  </label>
{/if}
<div class="note">{t('The playlist stays the same in Navidrome, with the same file and the same ID – Symfonium won’t notice. The original is backed up before it is overwritten for the first time.')}</div>
