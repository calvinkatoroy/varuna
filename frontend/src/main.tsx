import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '@fontsource/outfit/300.css'
import '@fontsource/outfit/400.css'
import '@fontsource/outfit/500.css'
import '@fontsource/outfit/600.css'
import '@fontsource/outfit/700.css'
import '@fontsource/outfit/800.css'
import App from './App'
import { AuthProvider } from './auth'
import './index.css'

// Theme: DARK is default; a saved 'light' choice (toggle) opts into the light look.
try {
  if (localStorage.getItem('varuna-theme') === 'light')
    document.documentElement.setAttribute('data-theme', 'light')
} catch {}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
