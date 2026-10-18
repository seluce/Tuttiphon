<!-- Pages for administrators only – users get a friendly hint. -->
<script>
  import Empty from '../components/Empty.svelte'
  import { t } from '../lib/i18n.svelte.js'
</script>

<div class="page">
  <Empty icon="lock" title={t('The administrator manages this')}
    text={t('This page concerns the whole family. Everything important for you is under “For you” and “My profile”.')}>
    <a class="btn primary" href="#/">{t('Go to “For you”')}</a>
  </Empty>
</div>
