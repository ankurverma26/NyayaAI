import { useEffect, useState } from 'react'
import Analysis from './components/Analysis'
import Dashboard from './components/Dashboard'
import LegalChanges from './components/LegalChanges'
import QAChat from './components/QAChat'
import { DISCLAIMER, Empty, Icon, Logo, ThemeToggle } from './components/ui'
import { Link, navigate, useLocation } from './router'

const contractFromSearch = (search: string): number | null => {
  const n = Number(new URLSearchParams(search).get('contract'))
  return Number.isInteger(n) && n > 0 ? n : null
}

export default function App() {
  const { route, search } = useLocation()
  // the contract most recently opened (used to scope the Q&A page); survives refresh via ?contract=N
  const [lastContract, setLastContract] = useState<number | null>(() => contractFromSearch(window.location.search))
  useEffect(() => { if (route.name === 'analysis') setLastContract(route.id) }, [route])

  const qaContract = route.name === 'qa' ? contractFromSearch(search) ?? lastContract : null
  const qaPath = lastContract ? `/qa?contract=${lastContract}` : '/qa'

  const nav: { to: string; label: string; icon: string; active: boolean }[] = [
    { to: '/', label: 'Dashboard', icon: 'file', active: route.name === 'dashboard' || route.name === 'analysis' },
    { to: qaPath, label: 'Legal Q&A', icon: 'chat', active: route.name === 'qa' },
    { to: '/changes', label: 'Legal Changes', icon: 'bell', active: route.name === 'changes' },
  ]

  const brand = (
    <Link to="/" className="group flex items-center gap-3">
      <Logo className="h-9 w-9 shrink-0 transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-105" />
      <span className="font-display text-[22px] font-bold leading-none tracking-tight text-ink">Nyaya<span className="font-medium text-brand">AI</span></span>
    </Link>
  )

  return (
    <div className="flex h-full flex-col md:flex-row">
      {/* desktop: left sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-line bg-surface md:flex">
        <div className="px-6 pb-6 pt-7">{brand}</div>
        <nav className="flex flex-1 flex-col gap-1 px-3">
          {nav.map(n => (
            <Link key={n.label} to={n.to}
              className={`group relative flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-all ${n.active ? 'bg-brand/10 text-ink' : 'text-muted hover:bg-ink/5 hover:text-ink'}`}>
              <span className={`absolute left-0 top-2 bottom-2 w-[3px] rounded-full bg-brand transition-opacity ${n.active ? 'opacity-100' : 'opacity-0'}`} />
              <Icon name={n.icon} className={`h-[18px] w-[18px] transition-colors ${n.active ? 'text-brand' : 'text-faint group-hover:text-ink'}`} />
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="m-3 rounded-2xl border border-line bg-raised p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs leading-snug text-muted">Indian legal reasoning &amp; contract intelligence</p>
            <ThemeToggle />
          </div>
        </div>
      </aside>

      {/* mobile: compact top bar */}
      <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-2.5 md:hidden">
        {brand}
        <nav className="ml-auto flex gap-1">
          {nav.map(n => (
            <Link key={n.label} to={n.to} aria-label={n.label}
              className={`flex h-9 w-9 items-center justify-center rounded-xl transition ${n.active ? 'bg-brand/12 text-brand' : 'text-muted hover:bg-ink/5'}`}>
              <Icon name={n.icon} className="h-[18px] w-[18px]" />
            </Link>
          ))}
        </nav>
        <ThemeToggle />
      </header>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <main className="min-h-0 flex-1 overflow-y-auto">
          {route.name === 'dashboard' && <Dashboard onOpen={id => navigate(`/contracts/${id}`)} />}
          {route.name === 'analysis' && <Analysis key={route.id} contractId={route.id} onBack={() => navigate('/')} />}
          {route.name === 'qa' && <QAChat key={qaContract ?? 'general'} defaultContractId={qaContract} />}
          {route.name === 'changes' && <LegalChanges onOpenContract={id => navigate(`/contracts/${id}`)} />}
          {route.name === 'notfound' && (
            <div className="mx-auto max-w-xl p-10">
              <Empty>Page not found. <Link to="/" className="font-medium text-brand hover:underline">Back to the dashboard</Link></Empty>
            </div>
          )}
        </main>
        <footer className="border-t border-line bg-surface px-6 py-2 text-center text-[11px] text-faint">{DISCLAIMER}</footer>
      </div>
    </div>
  )
}
