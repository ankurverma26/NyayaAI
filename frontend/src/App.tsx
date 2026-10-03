import { useEffect, useState } from 'react'
import Analysis from './components/Analysis'
import Dashboard from './components/Dashboard'
import LegalChanges from './components/LegalChanges'
import QAChat from './components/QAChat'
import { DISCLAIMER, Empty, Icon } from './components/ui'
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

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-6 border-b border-white/10 bg-[#0b0d13] px-6 py-3">
        <Link to="/" className="flex items-center gap-2">
          <Icon name="scale" className="h-6 w-6 text-amber-300" />
          <span className="font-serif text-2xl tracking-wide text-white">NyayaAI</span>
        </Link>
        <nav className="flex gap-1">
          {nav.map(n => (
            <Link key={n.label} to={n.to}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm ${n.active ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-slate-200'}`}>
              <Icon name={n.icon} /> {n.label}
            </Link>
          ))}
        </nav>
        <span className="ml-auto hidden text-xs text-slate-500 md:block">Indian Legal Reasoning &amp; Contract Intelligence</span>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto">
        {route.name === 'dashboard' && <Dashboard onOpen={id => navigate(`/contracts/${id}`)} />}
        {route.name === 'analysis' && <Analysis key={route.id} contractId={route.id} onBack={() => navigate('/')} />}
        {route.name === 'qa' && <QAChat key={qaContract ?? 'general'} defaultContractId={qaContract} />}
        {route.name === 'changes' && <LegalChanges onOpenContract={id => navigate(`/contracts/${id}`)} />}
        {route.name === 'notfound' && (
          <div className="mx-auto max-w-xl p-10">
            <Empty>Page not found. <Link to="/" className="text-amber-300 hover:underline">Back to the dashboard</Link></Empty>
          </div>
        )}
      </main>

      <footer className="border-t border-white/10 bg-[#0b0d13] px-6 py-2 text-center text-[11px] text-slate-500">{DISCLAIMER}</footer>
    </div>
  )
}
