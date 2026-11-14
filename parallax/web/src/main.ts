import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/noto-serif/400.css'
import '@fontsource/noto-serif/500.css'
import '@fontsource/jetbrains-mono/400.css'
import './app.css'
import { mount } from 'svelte'
import App from './App.svelte'

mount(App, { target: document.getElementById('app')! })
