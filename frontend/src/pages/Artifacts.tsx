import { useEffect, useMemo, useState } from 'react'
import {
  OFFLINE,
  addArtifact,
  deleteArtifact,
  getAdvice,
  getArtifacts,
  getCharacters,
  getScore,
  getSets,
  updateArtifact,
  type Advice,
  type Artifact,
  type ArtifactInput,
  type ArtifactSet,
  type Character,
  type Scores,
} from '../api/client'
import AdviceCard from '../components/AdviceCard'
import ArtifactForm from '../components/ArtifactForm'
import ArtifactList from '../components/ArtifactList'
import Combobox from '../components/Combobox'
import ImportButton from '../components/ImportButton'
import ScorePanel from '../components/ScorePanel'
import { useExpRate } from '../expRate'
import { buildLabel, nextCheck } from '../stats'

const COLLAPSED_KEY = 'inventory-collapsed'

function savedCollapsed() {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === '1'
  } catch {
    return false
  }
}

export default function Artifacts() {
  const [characters, setCharacters] = useState<Character[]>([])
  const [sets, setSets] = useState<ArtifactSet[]>([])
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [character, setCharacter] = useState('')
  const [selected, setSelected] = useState<number | null>(null)
  const [scores, setScores] = useState<Scores | null>(null)
  const [advice, setAdvice] = useState<{ key: string; value: Advice } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [version, setVersion] = useState(0)
  const [view, setView] = useState('all')
  const [collapsed, setCollapsed] = useState(savedCollapsed)

  const setNames = useMemo(() => new Map(sets.map((s) => [s.key, s.name])), [sets])

  const refresh = () => getArtifacts().then(setArtifacts)

  useEffect(() => {
    Promise.all([getCharacters(), getSets(), getArtifacts()])
      .then(([c, s, a]) => {
        setCharacters(c)
        setSets(s)
        setArtifacts(a)
      })
      .catch(() => setError(OFFLINE))
  }, [])

  useEffect(() => {
    if (selected !== null) getScore(selected, character).then(setScores)
  }, [selected, character, version])

  // advice needs one character: the one picked, else whoever the piece suits best
  const adviceFor = character || scores?.overall?.character_key || ''
  const [rate] = useExpRate()
  const adviceKey = `${selected}:${adviceFor}:${version}`
  useEffect(() => {
    if (selected !== null && adviceFor) getAdvice(selected, adviceFor, rate).then((value) => setAdvice({ key: adviceKey, value }))
  }, [selected, adviceFor, adviceKey, rate])
  const shown = advice?.key === adviceKey ? advice.value : null
  const current = artifacts.find((a) => a.id === selected)
  const next = current && shown ? nextCheck(current.level, shown.max_level) : 0

  const names = useMemo(() => new Map(characters.map((c) => [c.key, c.name])), [characters])
  const wearers = [...new Set(artifacts.map((a) => a.equipped_by).filter((k) => k !== null))].sort((a, b) =>
    (names.get(a) ?? a).localeCompare(names.get(b) ?? b),
  )
  const listed = artifacts.filter((a) => (view === 'all' ? true : view === 'loose' ? a.equipped_by === null : a.equipped_by === view))
  const picked = characters.find((c) => c.key === character)
  const preferred = picked && { label: `${picked.name}'s sets`, keys: [...new Set(picked.builds.flatMap((b) => b.sets))] }

  function toggleCollapsed() {
    setCollapsed(!collapsed)
    try {
      localStorage.setItem(COLLAPSED_KEY, collapsed ? '0' : '1')
    } catch {
      // not remembered, that's all
    }
  }

  function showFor(key: string) {
    setView(key)
    setCharacter(key)
  }

  function select(a: Artifact) {
    setSelected(a.id)
    setEditing(false)
  }

  async function save(input: ArtifactInput) {
    if (selected === null) return
    await updateArtifact(selected, input)
    setEditing(false)
    setVersion((v) => v + 1)
    await refresh()
  }

  async function add(input: ArtifactInput) {
    const result = await addArtifact(input, character)
    setSelected(result.id)
    setScores(result.scores)
    setEditing(false)
    await refresh()
  }

  async function remove(a: Artifact) {
    await deleteArtifact(a.id)
    if (selected === a.id) {
      setSelected(null)
      setScores(null)
    }
    await refresh()
  }

  if (error) return <p className="error">{error}</p>

  return (
    <div className="space-y-12">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <h1 className="font-display text-4xl">Artifacts</h1>
          <p className="mt-1 text-sm text-ink-2">Score any piece against every build, or bring in a GOOD export.</p>
        </div>
        <div className="flex flex-wrap items-center gap-6 text-sm">
          <label className="flex items-center gap-2">
            <span className="text-ink-2">Building for</span>
            <Combobox
              className="w-52"
              options={[{ value: '', label: 'everyone' }, ...characters.map((c) => ({ value: c.key, label: c.name }))]}
              value={character}
              onChange={setCharacter}
              aria-label="Building for"
            />
          </label>
          <ImportButton onDone={refresh} />
        </div>
      </div>

      <div className="grid gap-12 md:grid-cols-[1.1fr_1fr]">
        <ArtifactForm sets={sets} onSubmit={add} preferred={preferred} />
        <div className="space-y-10">
          <ScorePanel scores={scores} />
          {shown && (
            <div className="md:border-l md:border-rule md:pl-10">
              <p className="label mb-3">
                Levelling, for {shown.character} <span className="normal-case tracking-normal text-ink-3">{buildLabel(shown.build)}</span>
              </p>
              {editing && current ? (
                <ArtifactForm sets={sets} initial={{ ...current, level: next }} onSubmit={save} submitLabel={`Save +${next}`} preferred={preferred} />
              ) : (
                <AdviceCard advice={shown} />
              )}
              {current && shown.action !== 'done' && (
                <button onClick={() => setEditing(!editing)} className="link mt-4 text-xs">
                  {editing ? 'Cancel' : `I levelled it to +${next}`}
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      <section>
        <div className="mb-3 flex items-baseline justify-between gap-4">
          <h2 className="label">
            Inventory <span className="num normal-case">{artifacts.length}</span>
          </h2>
          <button onClick={toggleCollapsed} className="link text-xs">
            {collapsed ? 'Show' : 'Hide'}
          </button>
        </div>
        {!collapsed && (
          <>
            <nav className="mb-4 flex flex-wrap gap-x-5 gap-y-2 text-sm" aria-label="Whose artifacts">
              {[
                { key: 'all', label: 'All' },
                { key: 'loose', label: 'Not worn' },
                ...wearers.map((k) => ({ key: k, label: names.get(k) ?? k })),
              ].map((v) => (
                <button
                  key={v.key}
                  onClick={() => (v.key === 'all' || v.key === 'loose' ? setView(v.key) : showFor(v.key))}
                  className={`border-b-2 pb-0.5 ${view === v.key ? 'border-ink text-ink' : 'border-transparent text-ink-3 hover:text-ink'}`}
                >
                  {v.label}
                </button>
              ))}
            </nav>
            <ArtifactList artifacts={listed} setNames={setNames} characterNames={names} selected={selected} onSelect={select} onDelete={remove} />
          </>
        )}
      </section>
    </div>
  )
}
