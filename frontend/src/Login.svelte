<!-- Sign-in with the Navidrome account – or as local administrator (TUTTIPHON_ADMIN_PASSWORD). -->
<script>
  import { untrack } from 'svelte'
  import Icon from './components/Icon.svelte'
  import { t, lang } from './lib/i18n.svelte.js'
  import { appHash } from './lib/api.js'

  const NORMAL_SUB = $derived(t('Sign in with your Navidrome account – with the same name and password as in Symfonium.'))
  let notfall = $state(false)
  let username = $state('')
  let password = $state('')
  let remember = $state(true)
  let show = $state(false)
  let busy = $state(false)
  let error = $state('')
  let userInput = $state()
  let pwInput = $state()

  // after signing in: to the address that was asked for (#/playlist/…), otherwise the home page
  const target = '/' + appHash()
  // No sign-in needed at all (or already signed in)? Then go straight on.
  fetch('/api/me', { headers: { 'X-Tuttiphon': '1' } }).then((r) => { if (r.ok) location.replace(target) }).catch(() => {})
  try { username = localStorage.getItem('tuttiphon-user') || '' } catch { /* private mode */ }
  // only when opening: with a remembered name go straight to the password field – not on every typed letter
  $effect(() => { (untrack(() => username) ? pwInput : userInput)?.focus() })
  $effect(() => { document.title = t('Tuttiphon – Sign in') })

  function toggleMode() {
    notfall = !notfall
    error = ''
    password = ''
    pwInput?.focus()
  }

  async function submit(e) {
    e.preventDefault()
    // password managers sometimes fill in values without an input event – so read straight from the fields
    if (userInput && userInput.value !== username) username = userInput.value
    if (pwInput && pwInput.value !== password) password = pwInput.value
    const name = notfall ? '' : username.trim()
    if (!notfall && !name) { error = t('Please enter your username.'); userInput?.focus(); return }
    if (!password) { error = t('Please enter the password.'); pwInput?.focus(); return }
    busy = true
    error = ''
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Tuttiphon': '1', 'X-Lang': lang() },   // messages in this language
        body: JSON.stringify({ username: name, password, remember: notfall ? false : remember }),
      })
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        try { if (name) localStorage.setItem('tuttiphon-user', name) } catch { /* does not matter */ }
        location.replace(target)
        return
      }
      error = data.error || (res.status === 429 ? t('Too many failed attempts – please try again in a few minutes.') : t('Signing in did not work.'))
      pwInput?.select()
    } catch {
      error = t('Tuttiphon cannot be reached right now. Please try again shortly.')
    }
    busy = false
  }
</script>

<div class="min-h-screen grid place-items-center p-4 login-bg">
  <form class="w-[min(380px,100%)] px-[26px] py-[30px] rounded-3xl bg-surface border border-line-2 shadow-[0_30px_80px_rgba(0,0,0,.35)] grid gap-3.5"
    method="post" action="/api/login" id="login" name="login" novalidate onsubmit={submit}>
    <div class="grid justify-items-center gap-1.5 text-center mb-1">
      <img src="/favicon.svg" alt="" class="size-[60px]" />
      <h1 class="text-[1.5rem]">Tuttiphon</h1>
      <p class="muted text-[.92rem]">{notfall ? t('Tuttiphon’s own administrator – works without Navidrome.') : NORMAL_SUB}</p>
    </div>
    {#if !notfall}
      <div class="grid gap-1.5">
        <label for="username" class="font-semibold text-[.9rem]">{t('Username')}</label>
        <input bind:this={userInput} bind:value={username} id="username" name="username" class="input py-3" type="text"
          autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false" required />
      </div>
    {/if}
    <div class="grid gap-1.5">
      <label for="password" class="font-semibold text-[.9rem]">{notfall ? t('Administrator password') : t('Password')}</label>
      <span class="relative">
        <input bind:this={pwInput} bind:value={password} id="password" name="password" class="input py-3 w-full pr-11"
          type={show ? 'text' : 'password'} autocomplete="current-password" required />
        <button type="button" class="absolute right-1.5 top-1/2 -translate-y-1/2 p-2 rounded-lg text-muted hover:text-text"
          aria-label={show ? t('Hide password') : t('Show password')} title={show ? t('Hide password') : t('Show password')}
          onclick={() => { show = !show; pwInput?.focus() }}><Icon name={show ? 'eye-off' : 'eye'} /></button>
      </span>
    </div>
    {#if !notfall}
      <label class="grid grid-cols-[20px_1fr] gap-2.5 items-start text-[.88rem] text-muted cursor-pointer">
        <input type="checkbox" name="remember" bind:checked={remember} class="size-[18px] mt-0.5 accent-accent" />
        <span><b class="text-text font-semibold">{t('Turn on statistics & stars')}</b><br />{t('For this, Tuttiphon remembers your password – only on your NAS.')}</span>
      </label>
    {/if}
    <button class="btn primary py-[13px]" disabled={busy}>{busy ? t('One moment …') : t('Sign in')}</button>
    {#if error}<div class="err-t text-[.9rem] text-center" role="alert">{error}</div>{/if}
    <button type="button" class="link underline underline-offset-[3px] justify-self-center p-1 font-normal" onclick={toggleMode}>
      {notfall ? t('Back to normal sign-in') : t('Local administrator')}
    </button>
    {#if notfall}
      <p class="text-[.82rem] muted text-center">{t('The password set in docker-compose.yaml during setup. The local administrator has all rights and works even when Navidrome cannot be reached.')}</p>
    {/if}
  </form>
</div>

<style>
  .login-bg {
    background: radial-gradient(900px 500px at 10% 0%, rgba(139, 92, 246, .30), transparent 60%),
      radial-gradient(800px 500px at 100% 100%, rgba(236, 72, 153, .22), transparent 60%), var(--bg);
  }
</style>
