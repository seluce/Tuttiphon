<!-- Sign-in with the Navidrome account – or as local administrator. First start without an administrator password:
     setup code from the container log + new password (POST /api/setup). -->
<script>
  import { tick, untrack } from 'svelte'
  import Icon from './components/Icon.svelte'
  import { t, lang } from './lib/i18n.svelte.js'
  import { appHash } from './lib/api.js'

  const NORMAL_SUB = $derived(t('Sign in with your Navidrome account – with the same name and password as in Symfonium.'))
  let notfall = $state(false)
  let adminOnly = $state(false)   // not connected to Navidrome yet: only the local administrator can sign in
  let firstStart = $state(false)  // no administrator password yet: setup code + new password
  let code = $state('')
  let password2 = $state('')
  let username = $state('')
  let password = $state('')
  let remember = $state(true)
  let show = $state(false)
  let busy = $state(false)
  let error = $state('')
  let userInput = $state()
  let pwInput = $state()
  let pw2Input = $state()
  let codeInput = $state()

  // after signing in: to the address that was asked for (#/playlist/…), otherwise the home page
  const target = '/' + appHash()
  // No sign-in needed at all (or already signed in)? Then go straight on.
  fetch('/api/me', { headers: { 'X-Tuttiphon': '1' } }).then((r) => { if (r.ok) location.replace(target) }).catch(() => {})
  try { username = localStorage.getItem('tuttiphon-user') || '' } catch { /* private mode */ }
  // first start: set the administrator password; not connected to Navidrome yet: straight to the local administrator
  fetch('/api/login').then((r) => (r.ok ? r.json() : null)).then(async (d) => {
    if (d?.setup) {
      firstStart = notfall = true
      await tick()
      codeInput?.focus()
    } else if (d?.navidrome === false) {
      adminOnly = notfall = true
      await tick()
      pwInput?.focus()
    }
  }).catch(() => {})
  // only when opening: with a remembered name go straight to the password field – not on every typed letter
  $effect(() => { (untrack(() => username) ? pwInput : userInput)?.focus() })
  $effect(() => { document.title = t('Tuttiphon – Sign in') })

  function toggleMode() {
    notfall = !notfall
    error = ''
    password = ''
    pwInput?.focus()
  }

  async function submitSetup() {
    if (codeInput && codeInput.value !== code) code = codeInput.value
    if (pw2Input && pw2Input.value !== password2) password2 = pw2Input.value
    if (!code.trim()) { error = t('Please enter the setup code.'); codeInput?.focus(); return }
    if (password.length < 8) { error = t('The password needs at least 8 characters.'); pwInput?.focus(); return }
    if (password !== password2) { error = t('The two passwords are not the same.'); pw2Input?.focus(); return }
    busy = true
    error = ''
    try {
      const res = await fetch('/api/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Tuttiphon': '1', 'X-Lang': lang() },
        body: JSON.stringify({ code, password }),
      })
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        location.replace(target)   // signed in as local administrator – the setup assistant takes over
        return
      }
      error = data.error || (res.status === 429 ? t('Too many failed attempts – please try again in a few minutes.') : t('Signing in did not work.'))
    } catch {
      error = t('Tuttiphon cannot be reached right now. Please try again shortly.')
    }
    busy = false
  }

  async function submit(e) {
    e.preventDefault()
    // password managers sometimes fill in values without an input event – so read straight from the fields
    if (userInput && userInput.value !== username) username = userInput.value
    if (pwInput && pwInput.value !== password) password = pwInput.value
    if (firstStart) return submitSetup()
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
      <p class="muted text-[.92rem]">{firstStart ? t('Welcome! First set the password of the local administrator – Tuttiphon’s own administrator with all rights.')
        : adminOnly ? t('Not set up yet: sign in as local administrator – the setup assistant then connects Tuttiphon to Navidrome.')
        : notfall ? t('Tuttiphon’s own administrator – works without Navidrome.') : NORMAL_SUB}</p>
    </div>
    {#if firstStart}
      <div class="grid gap-1.5">
        <label for="code" class="font-semibold text-[.9rem]">{t('Setup code')}</label>
        <input bind:this={codeInput} bind:value={code} id="code" name="code" class="input py-3 font-mono tracking-[.15em] uppercase"
          type="text" autocomplete="one-time-code" autocapitalize="characters" autocorrect="off" spellcheck="false" placeholder="XXXX-XXXX" required /><!-- i18n-ignore: format of the code -->
        <span class="text-[.8rem] muted">{t('It is in the container log – in the Docker app of your NAS under the container’s log – and in the file setup-code.txt in Tuttiphon’s data folder.')}</span>
      </div>
    {/if}
    {#if !notfall}
      <div class="grid gap-1.5">
        <label for="username" class="font-semibold text-[.9rem]">{t('Username')}</label>
        <input bind:this={userInput} bind:value={username} id="username" name="username" class="input py-3" type="text"
          autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false" required />
      </div>
    {/if}
    <div class="grid gap-1.5">
      <label for="password" class="font-semibold text-[.9rem]">{firstStart ? t('New administrator password') : notfall ? t('Administrator password') : t('Password')}</label>
      <span class="relative">
        <input bind:this={pwInput} bind:value={password} id="password" name="password" class="input py-3 w-full pr-11"
          type={show ? 'text' : 'password'} autocomplete={firstStart ? 'new-password' : 'current-password'} required />
        <button type="button" class="absolute right-1.5 top-1/2 -translate-y-1/2 p-2 rounded-lg text-muted hover:text-text"
          aria-label={show ? t('Hide password') : t('Show password')} title={show ? t('Hide password') : t('Show password')}
          onclick={() => { show = !show; pwInput?.focus() }}><Icon name={show ? 'eye-off' : 'eye'} /></button>
      </span>
    </div>
    {#if firstStart}
      <div class="grid gap-1.5">
        <label for="password2" class="font-semibold text-[.9rem]">{t('Repeat password')}</label>
        <input bind:this={pw2Input} bind:value={password2} id="password2" name="password2" class="input py-3 w-full"
          type={show ? 'text' : 'password'} autocomplete="new-password" required />
      </div>
    {/if}
    {#if !notfall}
      <label class="grid grid-cols-[20px_1fr] gap-2.5 items-start text-[.88rem] text-muted cursor-pointer">
        <input type="checkbox" name="remember" bind:checked={remember} class="size-[18px] mt-0.5 accent-accent" />
        <span><b class="text-text font-semibold">{t('Turn on statistics & stars')}</b><br />{t('For this, Tuttiphon remembers your password – only on your NAS.')}</span>
      </label>
    {/if}
    <button class="btn primary py-[13px]" disabled={busy}>{busy ? t('One moment …') : firstStart ? t('Set password and sign in') : t('Sign in')}</button>
    {#if error}<div class="err-t text-[.9rem] text-center" role="alert">{error}</div>{/if}
    {#if !adminOnly && !firstStart}
      <button type="button" class="link underline underline-offset-[3px] justify-self-center p-1 font-normal" onclick={toggleMode}>
        {notfall ? t('Back to normal sign-in') : t('Local administrator')}
      </button>
    {/if}
    {#if firstStart}
      <p class="text-[.82rem] muted text-center">{t('At least 8 characters. Keep it safe, e.g. in a password manager – it is the way in when Navidrome cannot be reached. After that, the setup assistant connects Navidrome.')}</p>
    {:else if notfall}
      <p class="text-[.82rem] muted text-center">{t('The password set during setup. The local administrator has all rights and works even when Navidrome cannot be reached.')}</p>
    {/if}
  </form>
</div>

<style>
  .login-bg {
    background: radial-gradient(900px 500px at 10% 0%, rgba(139, 92, 246, .30), transparent 60%),
      radial-gradient(800px 500px at 100% 100%, rgba(236, 72, 153, .22), transparent 60%), var(--bg);
  }
</style>
