import { useId, useState } from 'react'
import type { ComponentType, ReactNode } from 'react'
import * as Lucide from 'lucide-react'
import type { RiskLevel } from '../types'

/* Icons are looked up by name (with fallbacks for renamed icons) so a missing icon never crashes the app. */
const ICONS: Record<string, string[]> = {
  check: ['CircleCheck', 'CheckCircle2'],
  warn: ['TriangleAlert', 'AlertTriangle'],
  fail: ['CircleX', 'XCircle'],
  spin: ['LoaderCircle', 'Loader2'],
  upload: ['Upload'], file: ['FileText'], scale: ['Scale'], search: ['Search'], send: ['Send'],
  close: ['X'], chat: ['MessageSquare'], bell: ['Bell'], shield: ['ShieldCheck'],
  sun: ['Sun'], moon: ['Moon'], down: ['ChevronDown'], right: ['ChevronRight'], dot: ['Circle'],
}

type IconComponent = ComponentType<{ className?: string }>

export function Icon({ name, className = 'h-4 w-4' }: { name: keyof typeof ICONS | string; className?: string }) {
  const lib = Lucide as unknown as Record<string, IconComponent | undefined>
  const found = (ICONS[name] ?? []).map(n => lib[n]).find(Boolean)
  const C = found
  return C ? <C className={className} /> : <span className={className}>•</span>
}


/** NyayaAI mark: an "N" whose diagonal is a balance beam, pivoting on a violet node (the AI at the fulcrum of justice). */
export function Logo({ className = 'h-9 w-9' }: { className?: string }) {
  const id = useId()
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className} role="img" aria-label="NyayaAI">
      <defs>
        <linearGradient id={`${id}-b`} x1="4" y1="2" x2="36" y2="38" gradientUnits="userSpaceOnUse">
          <stop stopColor="#6ee7b7" /><stop offset="1" stopColor="#047857" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="36" height="36" rx="11" fill={`url(#${id}-b)`} />
      <rect x="2.5" y="2.5" width="35" height="35" rx="10.5" stroke="#fff" strokeOpacity=".28" />
      <path d="M12.5 28.5v-17M27.5 28.5v-17M12.5 11.5l15 17" stroke="#03120c" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="20" cy="20" r="3.4" fill="#8b5cf6" stroke="#fff" strokeWidth="1.6" />
    </svg>
  )
}

/** Light/dark switch. Presentation-only: the theme lives on <html data-theme> and in localStorage. */
export function ThemeToggle({ className = '' }: { className?: string }) {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme ?? 'dark')
  const flip = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    try { localStorage.setItem('nyaya-theme', next) } catch { /* storage unavailable */ }
    setTheme(next)
  }
  return (
    <button onClick={flip} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`} title="Toggle theme"
      className={`flex h-9 w-9 items-center justify-center rounded-xl border border-line-strong bg-surface text-muted transition hover:border-brand hover:text-brand ${className}`}>
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} className="h-4 w-4" />
    </button>
  )
}

export const RISK: Record<RiskLevel, { label: string; badge: string; dot: string; rank: number }> = {
  high: { label: 'Critical Review', badge: 'bg-bad/10 text-bad border-bad/35', dot: 'bg-bad', rank: 3 },
  medium: { label: 'High Attention', badge: 'bg-hi/10 text-hi border-hi/35', dot: 'bg-hi', rank: 2 },
  low: { label: 'Moderate Attention', badge: 'bg-mod/10 text-mod border-mod/35', dot: 'bg-mod', rank: 1 },
  info: { label: 'Informational', badge: 'bg-info/10 text-info border-info/35', dot: 'bg-info', rank: 0 },
}

export function RiskBadge({ level }: { level: RiskLevel }) {
  const r = RISK[level] ?? RISK.info
  return <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${r.badge}`}><span className={`h-1.5 w-1.5 rounded-full ${r.dot}`} />{r.label}</span>
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted">
      <Icon name="spin" className="h-4 w-4 animate-spin text-brand" /> {label ?? 'Loading…'}
    </div>
  )
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-bad/30 bg-bad/10 p-4 text-sm text-bad backdrop-blur-md">
      <Icon name="warn" className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">{message}</div>
      {onRetry && <button onClick={onRetry} className="rounded-md border border-bad/40 px-2.5 py-0.5 text-xs transition hover:bg-bad/20">Retry</button>}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-dashed border-line-strong bg-ink/[0.02] p-8 text-center text-sm text-muted">{children}</div>
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-line bg-surface shadow-card ${className}`}>{children}</div>
}

export function VerifyBadge({ status }: { status: string | null }) {
  const ok = status === 'verified'
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${ok ? 'border-ok/35 bg-ok/10 text-ok' : 'border-warn/35 bg-warn/10 text-warn'}`}>
      <Icon name={ok ? 'check' : 'warn'} className="h-3 w-3" />
      {ok ? 'Verified' : status === 'no_statutory_source_expected' ? 'Clause-based finding' : 'Source verification required'}
    </span>
  )
}

export function Quote({ children }: { children: ReactNode }) {
  return <blockquote className="mt-2 rounded-r-xl border-l-[3px] border-cite bg-cite/[0.07] px-4 py-3 font-serif text-[15px] leading-relaxed text-ink">“{children}”</blockquote>
}

/** Renders a trace "detail" object as readable key/value lines. */
export function Detail({ data }: { data: Record<string, unknown> }) {
  const fmt = (v: unknown): string =>
    v == null ? '—' : Array.isArray(v) ? v.map(fmt).join(', ') : typeof v === 'object' ? JSON.stringify(v) : String(v)
  const entries = Object.entries(data).filter(([k]) => k !== 'ms')
  return (
    <dl className="mt-1 space-y-1 text-xs text-muted">
      {entries.map(([k, v]) =>
        k === 'quote'
          ? <Quote key={k}>{fmt(v)}</Quote>
          : <div key={k}><dt className="inline capitalize text-faint">{k.replace(/_/g, ' ')}: </dt><dd className="inline whitespace-pre-wrap break-words text-ink/80">{fmt(v)}</dd></div>,
      )}
    </dl>
  )
}

export const DISCLAIMER =
  'This platform provides legal information and document analysis for research and educational purposes. It is not a substitute for advice from a qualified legal professional.'
