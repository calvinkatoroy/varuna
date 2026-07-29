import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './auth'
import './index.css'

// Theme: DARK is default on every load; a saved 'light' choice (toggle) opts into light.
try {
  const t = localStorage.getItem('varuna-theme') === 'light' ? 'light' : 'dark'
  document.documentElement.setAttribute('data-theme', t)
} catch {
  document.documentElement.setAttribute('data-theme', 'dark')
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
