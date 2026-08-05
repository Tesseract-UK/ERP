import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ClerkProvider } from '@clerk/clerk-react'
import App from './App'
import { AuthProvider } from './AuthContext'
import { ToastProvider } from './components/ui'
import './styles.css'

const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

if (!CLERK_PUBLISHABLE_KEY) {
  throw new Error('Missing VITE_CLERK_PUBLISHABLE_KEY — add it to frontend/.env')
}

// No React.StrictMode: its dev-only double-invoked effects race Clerk's
// local-dev session handshake (a real redirect, done once to sync a token
// since localhost can't share cookies with the clerk.accounts.dev domain)
// into a reload loop.
//
// No custom `navigate` prop either: routing Clerk's own internal redirects
// through React Router's navigate() intercepted Clerk's handshake and
// re-triggered it in a loop. Letting Clerk manage its own navigation is
// slightly less smooth (a real page load instead of client-side routing
// during the handshake) but reliable.
ReactDOM.createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY}>
      <AuthProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </AuthProvider>
    </ClerkProvider>
  </BrowserRouter>
)
