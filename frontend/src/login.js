import '@fontsource-variable/inter'
import './app.css'
import { mount } from 'svelte'
import Login from './Login.svelte'

export default mount(Login, { target: document.getElementById('app') })
