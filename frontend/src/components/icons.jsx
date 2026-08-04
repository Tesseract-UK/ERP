// Central icon set for the whole app — thin line icons only, no emoji anywhere.
export {
  LayoutDashboard, Clock, Plane, Home, PenLine, User, CheckSquare, Users,
  CalendarDays, IdCard, ClipboardList, BarChart3, Megaphone, Building2,
  ShieldCheck, Bell, Menu, Inbox, ChevronLeft, ChevronRight, AlertTriangle,
  Cake, CheckCircle2, Download, X, LogOut, ArrowRight, Eye, EyeOff,
} from 'lucide-react'

// Abstract cube mark — the app's logo glyph. Inherits color via currentColor.
export function Logo({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2.5 L20.5 7.2 V16.8 L12 21.5 L3.5 16.8 V7.2 Z"
            stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
      <path d="M12 2.5 V21.5 M3.5 7.2 L12 12 L20.5 7.2"
            stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}
