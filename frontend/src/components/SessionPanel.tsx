import { useEffect, useState, type FormEvent } from 'react'
import {
  OFFLINE,
  addRun,
  addSessionArtifact,
  endSession,
  getActiveSession,
  getAdvice,
  getCharacters,
  getDomains,
  startSession,
  updateArtifact,
  type Advice,
  type Artifact,
  type ArtifactInput,
  type Character,
  type Domain,
  type FarmSession,
} from '../api/client'
import AdviceCard from './AdviceCard'
import { useExpRate } from '../expRate'
import ArtifactForm from './ArtifactForm'
import Combobox from './Combobox'
import { SLOT_LABELS, buildLabel, formatStat, nextCheck, statLabel, type Slot } from '../stats'

type Pending = { id: number; domain: Domain }

function StartForm({ characters, domains, initial, initialDomain, onStarted }: {
  characters: Character[]
  domains: Domain[]
  initial: string
  initialDomain: string
  onStarted: (s: FarmSession) => void
}) {
  const [character, setCharacter] = useState(initial)
  const [buildId, setBuildId] = useState<number | undefined>()
  const [domain, setDomain] = useState(initialDomain)
  const [error, setError] = useState<string | null>(null)
  const builds = characters.find((c) => c.key === character)?.builds ?? []

  async function submit(e: FormEvent) {
    e.preventDefault()
    try {
      onStarted(await startSession(character, buildId, domain))
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <section className="space-y-4">
      <h2 className="font-display text-2xl">Start a session</h2>
      <form onSubmit={submit} className="flex flex-wrap items-center gap-3 text-sm">
        <Combobox
          className="w-48"
          options={characters.map((c) => ({ value: c.key, label: c.name }))}
          value={character}
          onChange={(key) => {
            setCharacter(key)
            setBuildId(undefined)
          }}
          placeholder="Character"
          required
          aria-label="Character"
        />
        {builds.length > 1 && (
          <select className="field" value={buildId ?? ''} onChange={(e) => setBuildId(e.target.value ? Number(e.target.value) : undefined)}>
            <option value="">best-fitting build</option>
            {builds.map((b) => (
              <option key={b.id} value={b.id}>
                {buildLabel(b.name)}
              </option>
            ))}
          </select>
        )}
        <Combobox
          className="w-72"
          options={[{ value: '', label: 'domain of the worn set' }, ...domains.map((d) => ({ value: d.key, label: d.name }))]}
          value={domain}
          onChange={setDomain}
          aria-label="Domain"
        />
        <button type="submit" className="btn">
          Start
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </section>
  )
}

function SessionArtifact({ artifact, sets, onSaved }: {
  artifact: Artifact
  sets: Domain['sets']
  onSaved: () => void
}) {
  const [advice, setAdvice] = useState<Advice | null>(null)
  const [editing, setEditing] = useState(false)
  const [version, setVersion] = useState(0)
  const [rate] = useExpRate()

  useEffect(() => {
    getAdvice(artifact.id, '', rate).then(setAdvice)
  }, [artifact.id, version, rate])

  async function save(input: ArtifactInput) {
    await updateArtifact(artifact.id, input)
    setEditing(false)
    setVersion((v) => v + 1)
    onSaved()
  }

  // the form opens at the next +4, so only the new roll needs typing and the advice is redone from there
  const next = advice ? nextCheck(artifact.level, advice.max_level) : artifact.level

  return (
    <li className="grid gap-x-10 gap-y-4 border-t border-rule py-6 md:grid-cols-[15rem_1fr]">
      <div className="space-y-1">
        <p className="font-medium">
          {SLOT_LABELS[artifact.slot as Slot]} <span className="num text-sm text-ink-3">+{artifact.level}</span>
        </p>
        <p className="text-sm text-ink-2">{statLabel(artifact.main_stat)}</p>
        <ul className="num space-y-0.5 pt-1 text-xs text-ink-2">
          {artifact.substats.map((s) => (
            <li key={s.key}>{formatStat(s)}</li>
          ))}
          {artifact.unactivated.map((s) => (
            <li key={s.key} className="text-ink-3" title="Inactive until +4">
              {formatStat(s)} (inactive)
            </li>
          ))}
        </ul>
        <button onClick={() => setEditing(!editing)} className="link pt-2 text-xs">
          {editing ? 'Cancel' : advice && advice.action !== 'done' ? `I levelled it to +${next}` : 'Edit'}
        </button>
      </div>
      <div>
        {editing ? (
          <ArtifactForm sets={sets} initial={{ ...artifact, level: next }} onSubmit={save} submitLabel={`Save +${next}`} />
        ) : advice ? (
          <AdviceCard advice={advice} />
        ) : (
          <p className="text-sm text-ink-3">Working it out...</p>
        )}
      </div>
    </li>
  )
}

function ActiveSession({ farm, domains, onChange }: {
  farm: FarmSession
  domains: Domain[]
  onChange: (s: FarmSession | null) => void
}) {
  const [domain, setDomain] = useState('')
  const [resin, setResin] = useState(20)
  const [fiveStars, setFiveStars] = useState(1)
  const [pending, setPending] = useState<Pending[]>([])
  const [nextId, setNextId] = useState(0)

  const byKey = new Map(domains.map((d) => [d.key, d]))
  const allSets = domains.flatMap((d) => d.sets)

  function changeResin(value: number) {
    setResin(value)
    setFiveStars(value === 40 ? 2 : 1)
  }

  async function logRun(e: FormEvent) {
    e.preventDefault()
    const updated = await addRun(farm.id, resin, fiveStars, domain)
    const runDomain = byKey.get(domain) ?? farm.domain
    setPending([...pending, ...Array.from({ length: fiveStars }, (_, i) => ({ id: nextId + i, domain: runDomain }))])
    setNextId(nextId + fiveStars)
    onChange(updated)
  }

  async function evaluate(p: Pending, input: ArtifactInput) {
    await addSessionArtifact(input, farm.id)
    setPending((list) => list.filter((x) => x.id !== p.id))
    onChange(await getActiveSession())
  }

  async function refresh() {
    onChange(await getActiveSession())
  }

  async function finish() {
    await endSession(farm.id)
    onChange(null)
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="label">Session in progress</p>
          <h2 className="font-display text-2xl">
            {farm.character} <span className="text-ink-3 italic">in</span> {farm.domain.name}
          </h2>
          <p className="text-sm text-ink-2">{buildLabel(farm.build)}</p>
        </div>
        <dl className="flex gap-8">
          {[
            ['resin', farm.resin],
            ['runs', farm.runs.length],
            ['5★', farm.five_stars],
          ].map(([label, value]) => (
            <div key={label} className="text-right">
              <dd className="num text-2xl">{value}</dd>
              <dt className="label">{label}</dt>
            </div>
          ))}
        </dl>
      </div>

      <form onSubmit={logRun} className="flex flex-wrap items-center gap-x-3 gap-y-2 border-y border-rule py-4 text-sm">
        <span className="text-ink-2">Finished</span>
        <Combobox
          className="w-72"
          options={[
            { value: '', label: farm.domain.name },
            ...domains.filter((d) => d.key !== farm.domain.key).map((d) => ({ value: d.key, label: d.name })),
          ]}
          value={domain}
          onChange={setDomain}
          aria-label="Domain"
        />
        <span className="text-ink-2">for</span>
        <span className="inline-flex">
          {[20, 40].map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => changeResin(r)}
              className={`num border px-2.5 py-1.5 first:rounded-l-[3px] last:rounded-r-[3px] ${
                resin === r ? 'border-ink bg-ink text-paper' : 'border-rule-strong text-ink-2 hover:text-ink'
              }`}
            >
              {r}
            </button>
          ))}
        </span>
        <span className="text-ink-2">resin, got</span>
        <input
          className="field num w-14"
          type="number"
          min={0}
          max={10}
          value={fiveStars}
          onChange={(e) => setFiveStars(Math.max(0, Math.min(10, Number(e.target.value))))}
          aria-label="Five-star artifacts"
        />
        <span className="text-ink-2">five-star</span>
        <button type="submit" className="btn ml-1">
          Log run
        </button>
        <button type="button" onClick={finish} className="link ml-auto text-xs text-ink-3">
          End session
        </button>
      </form>

      <ul className="[&>li:first-child]:border-t-0">
        {pending.map((p, i) => (
          <li key={p.id} className="grid gap-x-10 gap-y-4 border-t border-rule py-6 md:grid-cols-[15rem_1fr]">
            <div>
              <p className="font-medium">New artifact{pending.length > 1 && <span className="num text-ink-3"> {i + 1}/{pending.length}</span>}</p>
              <p className="text-sm text-ink-3">{p.domain.name}</p>
            </div>
            <ArtifactForm sets={p.domain.sets} onSubmit={(input) => evaluate(p, input)} submitLabel="Evaluate" />
          </li>
        ))}
        {[...farm.artifacts].reverse().map((a) => (
          <SessionArtifact key={a.id} artifact={a} sets={allSets} onSaved={refresh} />
        ))}
      </ul>
      {pending.length === 0 && farm.artifacts.length === 0 && (
        <p className="text-sm text-ink-3">Log a run and the artifacts it dropped will show up here for evaluation.</p>
      )}
    </section>
  )
}

type Props = {
  initialCharacter: string
  initialDomain: string
  onActiveChange: (active: boolean) => void
}

export default function SessionPanel({ initialCharacter, initialDomain, onActiveChange }: Props) {
  const [farm, setFarm] = useState<FarmSession | null | undefined>(undefined)
  const [characters, setCharacters] = useState<Character[]>([])
  const [domains, setDomains] = useState<Domain[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (farm !== undefined) onActiveChange(farm !== null)
  }, [farm, onActiveChange])

  useEffect(() => {
    Promise.all([getActiveSession(), getCharacters(), getDomains()])
      .then(([f, c, d]) => {
        setFarm(f)
        setCharacters(c)
        setDomains(d)
      })
      .catch(() => setError(OFFLINE))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (farm === undefined) return null
  if (farm === null) {
    return <StartForm characters={characters} domains={domains} initial={initialCharacter} initialDomain={initialDomain} onStarted={setFarm} />
  }
  return <ActiveSession farm={farm} domains={domains} onChange={setFarm} />
}
