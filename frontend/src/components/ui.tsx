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
  down: ['ChevronDown'], right: ['ChevronRight'], dot: ['Circle'],
}

type IconComponent = ComponentType<{ className?: string }>

export function Icon({ name, className = 'h-4 w-4' }: { name: keyof typeof ICONS | string; className?: string }) {
  const lib = Lucide as unknown as Record<string, IconComponent | undefined>
  const found = (ICONS[name] ?? []).map(n => lib[n]).find(Boolean)
  const C = found
  return C ? <C className={className} /> : <span className={className}>•</span>
}

export const RISK: Record<RiskLevel, { label: string; badge: string; dot: string; rank: number }> = {
  high: { label: 'Critical Review', badge: 'bg-red-500/15 text-red-300 border-red-500/40', dot: 'bg-red-500', rank: 3 },
  medium: { label: 'High Attention', badge: 'bg-orange-500/15 text-orange-300 border-orange-500/40', dot: 'bg-orange-400', rank: 2 },
  low: { label: 'Moderate Attention', badge: 'bg-yellow-500/15 text-yellow-200 border-yellow-500/40', dot: 'bg-yellow-400', rank: 1 },
  info: { label: 'Informational', badge: 'bg-sky-500/15 text-sky-300 border-sky-500/40', dot: 'bg-sky-400', rank: 0 },
}

export function RiskBadge({ level }: { level: RiskLevel }) {
  const r = RISK[level] ?? RISK.info
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${r.badge}`}>{r.label}</span>
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-400">
      <Icon name="spin" className="h-4 w-4 animate-spin" /> {label ?? 'Loading…'}
    </div>
  )
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
      <Icon name="warn" className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">{message}</div>
      {onRetry && <button onClick={onRetry} className="rounded border border-red-400/40 px-2 py-0.5 text-xs hover:bg-red-500/20">Retry</button>}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border border-dashed border-white/15 p-6 text-center text-sm text-slate-400">{children}</div>
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-white/10 bg-[#161a23] ${className}`}>{children}</div>
}

export function VerifyBadge({ status }: { status: string | null }) {
  const ok = status === 'verified'
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${ok ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300' : 'border-amber-500/40 bg-amber-500/10 text-amber-200'}`}>
      <Icon name={ok ? 'check' : 'warn'} className="h-3 w-3" />
      {ok ? 'Verified' : status === 'no_statutory_source_expected' ? 'Clause-based finding' : 'Source verification required'}
    </span>
  )
}

export function Quote({ children }: { children: ReactNode }) {
  return <blockquote className="mt-2 border-l-2 border-amber-400/60 bg-black/20 px-3 py-2 font-serif text-sm leading-relaxed text-slate-200">“{children}”</blockquote>
}

/** Renders a trace "detail" object as readable key/value lines. */
export function Detail({ data }: { data: Record<string, unknown> }) {
  const fmt = (v: unknown): string =>
    v == null ? '—' : Array.isArray(v) ? v.map(fmt).join(', ') : typeof v === 'object' ? JSON.stringify(v) : String(v)
  const entries = Object.entries(data).filter(([k]) => k !== 'ms')
  return (
    <dl className="mt-1 space-y-1 text-xs text-slate-400">
      {entries.map(([k, v]) =>
        k === 'quote'
          ? <Quote key={k}>{fmt(v)}</Quote>
          : <div key={k}><dt className="inline capitalize text-slate-500">{k.replace(/_/g, ' ')}: </dt><dd className="inline whitespace-pre-wrap break-words text-slate-300">{fmt(v)}</dd></div>,
      )}
    </dl>
  )
}

export const DISCLAIMER =
  'This platform provides legal information and document analysis for research and educational purposes. It is not a substitute for advice from a qualified legal professional.'
