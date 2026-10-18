<!--
  One-time hint on the home pages: put Tuttiphon on the home screen as an app (lib/install.svelte.js).
  With the browser's install prompt a button, otherwise the matching instructions for iPhone or Android.
-->
<script>
  import Icon from './Icon.svelte'
  import { S } from '../lib/state.svelte.js'
  import { showHint, dismissHint, install, ios } from '../lib/install.svelte.js'
  import { t } from '../lib/i18n.svelte.js'
</script>

{#if showHint()}
  <div class="card flex gap-3.5 items-start mt-[18px]" role="note">
    <div class="hi shrink-0"><Icon name="smartphone" size={20} /></div>
    <div class="grid gap-2.5 min-w-0">
      <div>
        <b>{t('Tuttiphon as an app')}</b>
        <p class="muted small">
          {#if S.installPrompt}
            {t('Put Tuttiphon on your home screen. Then it opens like an app, without the browser bar.')}
          {:else if ios()}
            {t('Put Tuttiphon on your home screen: in Safari tap Share and then “Add to Home Screen”.')}
          {:else}
            {t('Put Tuttiphon on your home screen: in the browser menu ⋮ tap “Add to Home screen”.')}
          {/if}
        </p>
      </div>
      <div class="btns">
        {#if S.installPrompt}
          <button class="btn sm primary" onclick={install}><Icon name="plus" size={15} />{t('Install')}</button>
          <button class="btn sm ghost" onclick={dismissHint}>{t('Not now')}</button>
        {:else}
          <button class="btn sm" onclick={dismissHint}>{t('Got it')}</button>
        {/if}
      </div>
    </div>
  </div>
{/if}
