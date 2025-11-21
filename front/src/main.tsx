import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import BlockingPage from './components/BlockingPage'

// Simple hash-based routing
function Router() {
  const hash = window.location.hash

  if (hash === '#/blocking') {
    return <BlockingPage />
  }

  return <App />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Router />
  </StrictMode>,
)
