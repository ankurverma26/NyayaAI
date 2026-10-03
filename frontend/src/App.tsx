import { useState } from 'react'
import Analysis from './components/Analysis'
import Dashboard from './components/Dashboard'
import LegalChanges from './components/LegalChanges'
import QAChat from './components/QAChat'
import { DISCLAIMER, Icon } from './components/ui'

type View = 'dashboard' | 'analysis' | 'qa' | 'changes'

export default function App() {
  const [view, setView] = useState<View>('dashboard')
  const [contractId, setContractId] = useState<number | null>(null)

  const open = (id: number) => { setContractId(id); setView('analysis') }
  const nav: [View, string, string][] = [
    ['dashboard', 'Dashboard', 'file'],
    ['qa', 'Legal Q&A', 'chat'],
    ['changes', 'Legal Changes', 'bell'],
  ]

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-6 border-b border-white/10 bg-[#0b0d13] px-6 py-3">
        <button onClick={() => setView('dashboard')} className="flex items-center gap-2">
          <Icon name="scale" className="h-6 w-6 text-amber-300" />
          <span className="font-serif text-2xl tracking-wide text-white">NyayaAI</span>
        </button>
        <nav className="flex gap-1">
          {nav.map(([v, label, icon]) => (
            <button key={v} onClick={() => setView(v)}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm ${view === v || (v === 'dashboard' && view === 'analysis') ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-slate-200'}`}>
              <Icon name={icon} /> {label}
            </button>
          ))}
        </nav>
        <span className="ml-auto hidden text-xs text-slate-500 md:block">Indian Legal Reasoning &amp; Contract Intelligence</span>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto">
        {view === 'dashboard' && <Dashboard onOpen={open} />}
        {view === 'analysis' && contractId !== null && <Analysis contractId={contractId} onBack={() => setView('dashboard')} />}
        {view === 'qa' && <QAChat key={contractId ?? 'general'} defaultContractId={contractId} />}
        {view === 'changes' && <LegalChanges onOpenContract={open} />}
      </main>

      <footer className="border-t border-white/10 bg-[#0b0d13] px-6 py-2 text-center text-[11px] text-slate-500">{DISCLAIMER}</footer>
    </div>
  )
}
