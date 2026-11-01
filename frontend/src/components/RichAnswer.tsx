import type { ReactNode } from 'react'

/**
 * Renders an answer from /api/legal/ask.
 *
 * Supports exactly the small markdown subset the backend produces:
 *   ## heading · - bullets · 1. numbered items · > quotes · **bold** · blank-line paragraphs
 * Everything is built as React elements (no dangerouslySetInnerHTML), so model output can never inject
 * HTML. The older plain-text template answers (numbered provisions, "[HIGH] ..." lines) render fine too.
 * Known statutory citations are highlighted inline so they are easy to spot.
 */

type Block =
  | { kind: 'heading'; text: string }
  | { kind: 'quote'; text: string }
  | { kind: 'list'; ordered: boolean; items: { text: string; quote?: string }[] }
  | { kind: 'para'; text: string }

const HEADING = /^#{1,4}\s+(.+?)\s*#*\s*$/
const BULLET = /^\s{0,3}[-*•]\s+(.*)$/
const NUMBERED = /^\s{0,3}\d{1,2}[.)]\s+(.*)$/
const QUOTE = /^\s*>\s?(.*)$/
const INDENTED = /^\s{2,}\S/

export function parseAnswer(src: string): Block[] {
  const blocks: Block[] = []
  let para: string[] = []
  const flush = () => {
    if (para.length) blocks.push({ kind: 'para', text: para.join('\n') })
    para = []
  }
  for (const raw of src.replace(/\r/g, '').split('\n')) {
    const line = raw.replace(/\s+$/, '')
    if (!line.trim()) { flush(); continue }

    const h = HEADING.exec(line)
    if (h) { flush(); blocks.push({ kind: 'heading', text: h[1] }); continue }

    const last = blocks[blocks.length - 1]
    // an indented line (or an indented "> quote") directly under a list item belongs to that item
    if (!para.length && last?.kind === 'list' && INDENTED.test(raw)) {
      const item = last.items[last.items.length - 1]
      const q = QUOTE.exec(line.trim())
      if (q) item.quote = [item.quote, q[1]].filter(Boolean).join(' ')
      else item.quote = [item.quote, line.trim()].filter(Boolean).join(' ')
      continue
    }

    const b = BULLET.exec(line)
    const n = b ? null : NUMBERED.exec(line)
    if (b || n) {
      flush()
      const ordered = !!n
      const text = (b ?? n)![1]
      if (last?.kind === 'list' && last.ordered === ordered) last.items.push({ text })
      else blocks.push({ kind: 'list', ordered, items: [{ text }] })
      continue
    }

    const q = QUOTE.exec(line)
    if (q) {
      flush()
      if (last?.kind === 'quote') last.text += '\n' + q[1]
      else blocks.push({ kind: 'quote', text: q[1] })
      continue
    }
    para.push(line)
  }
  flush()
  return blocks
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

function inline(text: string, cites: RegExp | null, keyBase: string): ReactNode[] {
  // **bold** first, then citations inside every piece
  const out: ReactNode[] = []
  text.split(/(\*\*[^*]+\*\*)/g).forEach((piece, i) => {
    if (!piece) return
    const bold = piece.startsWith('**') && piece.endsWith('**') && piece.length > 4
    const body = bold ? piece.slice(2, -2) : piece
    const parts = cites ? body.split(cites) : [body]
    const nodes = parts.map((p, j) => (cites && j % 2 === 1)
      ? <span key={`${keyBase}-${i}-${j}`} className="rounded bg-cite/10 px-1 font-medium text-cite">{p}</span>
      : p)
    out.push(bold ? <strong key={`${keyBase}-${i}`} className="font-semibold">{nodes}</strong> : <span key={`${keyBase}-${i}`}>{nodes}</span>)
  })
  return out
}

export default function RichAnswer({ text, citations = [] }: { text: string; citations?: string[] }) {
  const unique = [...new Set(citations.filter(Boolean))].sort((a, b) => b.length - a.length)
  const cites = unique.length ? new RegExp(`(${unique.map(escapeRe).join('|')})`, 'g') : null
  const blocks = parseAnswer(text)

  return (
    <div className="space-y-3 text-[15px] leading-7 text-ink">
      {blocks.map((b, i) => {
        const k = `b${i}`
        switch (b.kind) {
          case 'heading':
            return <h3 key={k} className="mt-5 border-b border-line pb-1 font-display text-[13px] font-semibold uppercase tracking-wide text-brand first:mt-0">{b.text}</h3>
          case 'quote':
            return <blockquote key={k} className="rounded-r-xl border-l-[3px] border-warn bg-raised px-4 py-2 text-sm leading-relaxed text-muted">{inline(b.text, cites, k)}</blockquote>
          case 'list': {
            const List = b.ordered ? 'ol' : 'ul'
            return (
              <List key={k} className={`space-y-2 pl-5 ${b.ordered ? 'list-decimal' : 'list-disc'} marker:text-faint`}>
                {b.items.map((it, j) => (
                  <li key={j} className="pl-1">
                    {inline(it.text, cites, `${k}-${j}`)}
                    {it.quote && <div className="mt-1 rounded-r-lg border-l-[3px] border-cite bg-cite/[0.07] px-3 py-1.5 font-serif text-sm leading-relaxed text-ink">{inline(it.quote, null, `${k}-${j}q`)}</div>}
                  </li>
                ))}
              </List>
            )
          }
          default: {
            const isSources = /^Sources?:/.test(b.text)
            return <p key={k} className={`whitespace-pre-line ${isSources ? 'text-xs text-muted' : ''}`}>{inline(b.text, cites, k)}</p>
          }
        }
      })}
    </div>
  )
}
