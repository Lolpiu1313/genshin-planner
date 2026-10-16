import { useState } from 'react'
import Artifacts from './pages/Artifacts'
import Characters from './pages/Characters'
import Farm from './pages/Farm'

const PAGES = { farm: 'Farm', characters: 'Characters', artifacts: 'Artifacts' } as const
type Page = keyof typeof PAGES

export default function App() {
  const [page, setPage] = useState<Page>('farm')
  const [sessionCharacter, setSessionCharacter] = useState('')

  function startSessionFor(character: string) {
    setSessionCharacter(character)
    setPage('farm')
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-rule">
        <div className="mx-auto flex max-w-6xl flex-wrap items-end gap-x-12 gap-y-3 px-6 pt-7">
          <p className="pb-3 font-display text-2xl italic">Genshin Planner</p>
          <nav className="flex gap-7 text-sm">
            {(Object.keys(PAGES) as Page[]).map((p) => (
              <button
                key={p}
                onClick={() => setPage(p)}
                className={`border-b-2 pb-3 ${page === p ? 'border-ink text-ink' : 'border-transparent text-ink-3 hover:text-ink'}`}
              >
                {PAGES[p]}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-10">
        {page === 'farm' && <Farm key={sessionCharacter} initialCharacter={sessionCharacter} onGoToCharacters={() => setPage('characters')} />}
        {page === 'characters' && <Characters onStartSession={startSessionFor} />}
        {page === 'artifacts' && <Artifacts />}
      </main>
    </div>
  )
}
