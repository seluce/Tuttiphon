<!-- "My profile": straight to your own person – without one to the welcome assistant that creates it (the local
     administrator, who has no Navidrome account, to People). -->
<script>
  import { untrack } from 'svelte'
  import { S, myPerson } from '../lib/state.svelte.js'
  import { replace } from '../lib/router.svelte.js'

  $effect(() => {
    untrack(() => {
      const p = myPerson()
      // replacing: "back" must not lead here again
      replace(p ? `#/person/${p.id}` : S.me?.user && !S.me.notfall ? '#/willkommen' : '#/personen')   // i18n-ignore: routes
    })
  })
</script>
