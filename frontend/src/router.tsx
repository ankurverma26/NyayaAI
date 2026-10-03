import { useEffect, useState } from 'react'
import type { MouseEvent, ReactNode } from 'react'

/* Minimal history-API router (no extra dependency).
   /                -> dashboard
   /contracts/:id   -> contract analysis
   /qa[?contract=N] -> legal Q&A
   /changes         -> legal changes                                        */

export type Route =
  | { name: 'dashboard' }
  | { name: 'analysis'; id: number }
  | { name: 'qa' }
  | { name: 'changes' }
  | { name: 'notfound' }

export function parseRoute(pathname: string): Route {
  const p = pathname.replace(/\/+$/, '') || '/'
  if (p === '/') return { name: 'dashboard' }
  if (p === '/qa') return { name: 'qa' }
  if (p === '/changes') return { name: 'changes' }
  const m = p.match(/^\/contracts\/(\d+)$/)
  return m ? { name: 'analysis', id: Number(m[1]) } : { name: 'notfound' }
}

export function navigate(to: string): void {
  if (to === window.location.pathname + window.location.search) return
  window.history.pushState(null, '', to)
  window.dispatchEvent(new PopStateEvent('popstate'))
  window.scrollTo(0, 0)
}

export function useLocation(): { route: Route; search: string } {
  const read = () => ({ pathname: window.location.pathname, search: window.location.search })
  const [loc, setLoc] = useState(read)
  useEffect(() => {
    const onChange = () => setLoc(read())
    window.addEventListener('popstate', onChange) // back/forward buttons and navigate()
    return () => window.removeEventListener('popstate', onChange)
  }, [])
  return { route: parseRoute(loc.pathname), search: loc.search }
}

/** A real <a href>, so right-click / ctrl-click "open in new tab" still works. */
export function Link({ to, className, children }: { to: string; className?: string; children: ReactNode }) {
  const onClick = (e: MouseEvent<HTMLAnchorElement>) => {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
    e.preventDefault()
    navigate(to)
  }
  return <a href={to} onClick={onClick} className={className}>{children}</a>
}
