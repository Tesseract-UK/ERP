// Shared layout for the sign-in, sign-up and admin sign-in pages:
// a brand panel (left, hidden on small screens) and the form panel (right).
import { CalendarCheck, Logo, MapPin, MessageSquare } from './icons'

const FEATURES = [
  { icon: MapPin, title: 'One-tap attendance', text: 'Location-verified check-in that follows your shift, even past midnight.' },
  { icon: CalendarCheck, title: 'Leave & work from home', text: 'Apply in seconds, see your balance and the company calendar at a glance.' },
  { icon: MessageSquare, title: 'Approvals that talk back', text: 'Every request is a conversation — tag a colleague, get a decision.' },
]

// A wireframe tesseract: an outer and inner cube joined at the corners.
function TesseractArt() {
  const outer = [[60, 40], [200, 40], [200, 180], [60, 180]]
  const back = [[100, 80], [240, 80], [240, 220], [100, 220]]
  const inner = [[105, 85], [155, 85], [155, 135], [105, 135]]
  const innerBack = [[130, 110], [180, 110], [180, 160], [130, 160]]
  const sq = (p) => p.map(([x, y]) => `${x},${y}`).join(' ')
  const join = (a, b) => a.map(([x1, y1], i) => <line key={i} x1={x1} y1={y1} x2={b[i][0]} y2={b[i][1]} />)
  return (
    <svg className="auth-tesseract" viewBox="0 0 300 260" aria-hidden="true">
      <defs>
        <linearGradient id="tg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7cc0ff" />
          <stop offset="1" stopColor="#8b7bff" />
        </linearGradient>
      </defs>
      <g fill="none" stroke="url(#tg)" strokeWidth="1.4" strokeLinejoin="round">
        <polygon points={sq(outer)} opacity=".9" />
        <polygon points={sq(back)} opacity=".45" />
        {join(outer, back)}
        <polygon points={sq(inner)} opacity=".9" />
        <polygon points={sq(innerBack)} opacity=".5" />
        {join(inner, innerBack)}
        <g opacity=".35">{join(outer, inner)}{join(back, innerBack)}</g>
      </g>
      {[...outer, ...back].map(([x, y], i) => <circle key={i} cx={x} cy={y} r="2.6" fill="#9fd0ff" />)}
    </svg>
  )
}

export function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  )
}

export function GoogleButton({ onClick, busy, children }) {
  return (
    <button type="button" className="auth-google" onClick={onClick} disabled={busy} aria-busy={busy}>
      {busy ? <span className="auth-spinner" aria-hidden="true" /> : <GoogleMark />}
      <span>{busy ? 'Redirecting to Google…' : children}</span>
    </button>
  )
}

export function AuthAlert({ children }) {
  if (!children) return null
  return <div role="alert" className="auth-alert">{children}</div>
}

export default function AuthShell({ eyebrow, title, subtitle, children, footer }) {
  return (
    <div className="auth">
      <aside className="auth-brand">
        <div className="auth-aurora" aria-hidden="true"><i /><i /><i /></div>
        <div className="auth-grid" aria-hidden="true" />
        <div className="auth-brand-inner">
          <div className="auth-logo"><Logo size={26} /><span>Tesseract HRMS</span></div>
          <div className="auth-hero">
            <TesseractArt />
            <h2>Your whole workday,<br /><span>in one place.</span></h2>
            <ul className="auth-features">
              {FEATURES.map(({ icon: Icon, title: t, text }) => (
                <li key={t}>
                  <span className="auth-feature-icon"><Icon size={17} /></span>
                  <div><strong>{t}</strong><p>{text}</p></div>
                </li>
              ))}
            </ul>
          </div>
          <div className="auth-legal">© {new Date().getFullYear()} Tesseract · For Tesseract employees only</div>
        </div>
      </aside>

      <main className="auth-main">
        <div className="auth-panel">
          <div className="auth-logo auth-logo-mobile"><Logo size={24} /><span>Tesseract HRMS</span></div>
          {eyebrow && <div className="auth-eyebrow">{eyebrow}</div>}
          <h1>{title}</h1>
          {subtitle && <p className="auth-sub">{subtitle}</p>}
          {children}
          {footer && <div className="auth-footer">{footer}</div>}
        </div>
      </main>
    </div>
  )
}
