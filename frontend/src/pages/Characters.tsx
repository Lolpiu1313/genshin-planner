import { useEffect, useState, type FormEvent } from 'react'
import {
  OFFLINE,
  clearProfile,
  getCharacters,
  getProfile,
  getQueue,
  importEnka,
  removeQueue,
  saveQueue,
  type Character,
  type ProfileCharacter,
  type QueueItem,
} from '../api/client'
import CharacterEstimate from '../components/CharacterEstimate'
import Combobox from '../components/Combobox'
import Progress from '../components/Progress'
import { SLOTS, SLOT_LABELS, buildLabel, statLabel } from '../stats'

const UID_KEY = 'genshin-planner-uid'
const DEFAULT_TARGET = 45
const ROW = 'grid grid-cols-[1fr_auto] items-center gap-x-8 gap-y-3 md:grid-cols-[minmax(11rem,1.3fr)_4.5rem_minmax(13rem,1.6fr)_minmax(10rem,1fr)_7rem]'

function savedUid() {
  try {
    return localStorage.getItem(UID_KEY) ?? ''
  } catch {
    return ''
  }
}

function tone(score: number) {
  if (score >= 0.5) return 'text-good'
  if (score >= 0.35) return 'text-warn'
  return 'text-ink-2'
}

const KEY_STATS: [string, string, (v: number) => string][] = [
  ['hp', 'HP', (v) => Math.round(v).toLocaleString('en-US')],
  ['atk', 'ATK', (v) => Math.round(v).toLocaleString('en-US')],
  ['critRate_', 'Crit rate', (v) => `${v.toFixed(1)}%`],
  ['critDMG_', 'Crit DMG', (v) => `${v.toFixed(1)}%`],
  ['eleMas', 'EM', (v) => Math.round(v).toString()],
  ['enerRech_', 'ER', (v) => `${v.toFixed(0)}%`],
]

const SOURCE = {
  enka: "From your in-game stats and how this character's talents scale.",
  reference: "From how this character's talents scale, on a typically built character.",
  site: "From genshin-builds.com's substat priority.",
}

function Weights({ weights, source }: { weights: Record<string, number>; source: keyof typeof SOURCE }) {
  const sorted = Object.entries(weights).sort((a, b) => b[1] - a[1])
  return (
    <div className="space-y-2">
      <p className="label">What a roll is worth</p>
      <ul className="space-y-1.5">
        {sorted.map(([stat, w]) => (
          <li key={stat} className="grid grid-cols-[7.5rem_1fr_2.5rem] items-center gap-3 text-sm">
            <span className="truncate text-ink-2">{statLabel(stat)}</span>
            <span className="h-[3px] bg-rule">
              <span className="block h-full bg-mark" style={{ width: `${w * 100}%` }} />
            </span>
            <span className="num text-right text-xs text-ink-2">{w.toFixed(2)}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-ink-3">{SOURCE[source]}</p>
    </div>
  )
}

const SCORE_KIND = {
  damage: 'Damage your artifacts add, as a share of what flawless +20 pieces would add',
  pieces: 'Average score of the equipped pieces for this support build',
}

type Row = { key: string; name: string; profile?: ProfileCharacter; queued?: QueueItem }

function EnkaImport({ onDone }: { onDone: () => void }) {
  const [uid, setUid] = useState(savedUid)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      const r = await importEnka(uid.trim())
      try {
        localStorage.setItem(UID_KEY, uid.trim())
      } catch {
        // storage can be blocked; the UID just won't be remembered
      }
      const skipped = r.skipped ? `, ${r.skipped} skipped` : ''
      setMessage(`Imported ${r.characters.length} characters and ${r.artifacts} artifacts for ${r.nickname}${skipped}.`)
      onDone()
    } catch (err) {
      setMessage((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      <label className="label block" htmlFor="uid">
        Enka showcase
      </label>
      <div className="flex gap-2">
        <input
          id="uid"
          value={uid}
          onChange={(e) => setUid(e.target.value)}
          inputMode="numeric"
          pattern="[0-9]{9,10}"
          placeholder="UID"
          required
          className="field num w-36"
        />
        <button type="submit" disabled={busy} className="btn">
          {busy ? 'Importing' : 'Import'}
        </button>
      </div>
      {message && <p className="text-xs text-ink-2">{message}</p>}
    </form>
  )
}

function Slots({ p }: { p: ProfileCharacter }) {
  return (
    <ul className="grid grid-cols-5 gap-2">
      {SLOTS.map((s) => {
        const score = p.slots[s]?.score
        return (
          <li key={s} title={`${SLOT_LABELS[s]}: ${score ?? 'empty'}`}>
            <div className="h-[3px] bg-rule">
              <div className="h-full bg-mark" style={{ width: `${score ?? 0}%` }} />
            </div>
            <p className="num mt-1 text-[11px] text-ink-3">
              {SLOT_LABELS[s][0]} <span className={score ? 'text-ink-2' : ''}>{score === undefined ? '—' : Math.round(score)}</span>
            </p>
          </li>
        )
      })}
    </ul>
  )
}

function Details({ row, index, count, onSave, onMove, onRemove }: {
  row: Row
  index: number
  count: number
  onSave: (patch: { build_id?: number; target_score?: number }) => void
  onMove: (dir: -1 | 1) => void
  onRemove: () => void
}) {
  const { profile: p, queued: q } = row
  const weighted = q ?? p
  return (
    <div className="grid gap-x-12 gap-y-8 pt-2 pb-8 md:grid-cols-[16rem_1fr]">
      <div className="space-y-6">
        {weighted && <Weights weights={weighted.weights} source={weighted.weights_source} />}
        {p && (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            {KEY_STATS.map(([key, label, format]) => (
              <div key={key}>
                <dt className="label">{label}</dt>
                <dd className="num">{format(p.stats[key] ?? 0)}</dd>
              </div>
            ))}
          </dl>
        )}
        {q && (
          <div className="space-y-3 text-sm">
            <p className="label">In the queue</p>
            {q.builds.length > 1 && (
              <select className="field w-full" value={q.build_id} onChange={(e) => onSave({ build_id: Number(e.target.value) })} aria-label="Build">
                {q.builds.map((b) => (
                  <option key={b.id} value={b.id}>
                    {buildLabel(b.name)}
                  </option>
                ))}
              </select>
            )}
            <div className="flex items-center gap-3">
              <span className="text-ink-2">Target</span>
              <input
                type="number"
                min={0.05}
                max={1}
                step={0.01}
                defaultValue={(q.target_score / 100).toFixed(2)}
                onBlur={(e) => {
                  const value = Math.round(Number(e.target.value) * 100)
                  if (value > 0 && value !== q.target_score) onSave({ target_score: value })
                }}
                className="field num w-20"
                aria-label="Target build score"
              />
            </div>
            <div className="flex gap-4 text-xs">
              <button disabled={index === 0} onClick={() => onMove(-1)} className="link disabled:opacity-30">
                Move up
              </button>
              <button disabled={index === count - 1} onClick={() => onMove(1)} className="link disabled:opacity-30">
                Move down
              </button>
              <button onClick={onRemove} className="link text-bad">
                Remove
              </button>
            </div>
          </div>
        )}
      </div>
      <div>
        <p className="label mb-3">Resin to target</p>
        <CharacterEstimate
          key={`${q?.build_id}:${q?.target_score}`}
          character={row.key}
          buildId={q?.build_id ?? p?.build_id}
          target={q?.target_score ?? DEFAULT_TARGET}
        />
      </div>
    </div>
  )
}

export default function Characters({ onStartSession }: { onStartSession: (character: string) => void }) {
  const [characters, setCharacters] = useState<Character[]>([])
  const [profile, setProfile] = useState<ProfileCharacter[]>([])
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [open, setOpen] = useState<string | null>(null)
  const [adding, setAdding] = useState('')
  const [error, setError] = useState<string | null>(null)

  const refresh = () =>
    Promise.all([getProfile(), getQueue()]).then(([p, q]) => {
      setProfile(p)
      setQueue(q)
    })

  useEffect(() => {
    Promise.all([getCharacters(), getProfile(), getQueue()])
      .then(([c, p, q]) => {
        setCharacters(c)
        setProfile(p)
        setQueue(q)
      })
      .catch(() => setError(OFFLINE))
  }, [])

  const owned = new Map(profile.map((p) => [p.character_key, p]))
  const queued = new Set(queue.map((q) => q.character_key))
  // queued characters first, in priority order, then the rest of the showcase
  const rows: Row[] = [
    ...queue.map((q) => ({ key: q.character_key, name: q.character, profile: owned.get(q.character_key), queued: q })),
    ...profile.filter((p) => !queued.has(p.character_key)).map((p) => ({ key: p.character_key, name: p.character, profile: p })),
  ]

  async function save(item: QueueItem, patch: { build_id?: number; target_score?: number }) {
    await saveQueue({ character_key: item.character_key, target_score: item.target_score, ...patch })
    await refresh()
  }

  async function move(index: number, dir: -1 | 1) {
    const a = queue[index]
    const b = queue[index + dir]
    // positions in the list are the priorities, so swapping rewrites both
    await saveQueue({ character_key: a.character_key, target_score: a.target_score, priority: index + dir + 1 })
    await saveQueue({ character_key: b.character_key, target_score: b.target_score, priority: index + 1 })
    await refresh()
  }

  async function enqueue(key: string, buildId?: number) {
    await saveQueue({ character_key: key, build_id: buildId, target_score: DEFAULT_TARGET })
    await refresh()
  }

  async function clearAll() {
    if (!confirm('Remove all imported characters, the artifacts they wear and the queue? Artifacts you added yourself stay.')) return
    await clearProfile()
    setOpen(null)
    await refresh()
  }

  async function dequeue(key: string) {
    await removeQueue(key)
    setOpen(null)
    await refresh()
  }

  if (error) return <p className="error">{error}</p>

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-end justify-between gap-8">
        <div>
          <h1 className="font-display text-4xl">Characters</h1>
          <p className="mt-1 max-w-lg text-sm text-ink-2">
            Build scores are out of 1: the share of the damage flawless artifacts would add (for supports, how close each piece is to flawless). Queue the ones you are building, in order.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-8">
          <EnkaImport onDone={refresh} />
          <form
            onSubmit={(e) => {
              e.preventDefault()
              enqueue(adding).then(() => setAdding(''))
            }}
            className="space-y-2"
          >
            <label className="label block" htmlFor="add">
              Not in the showcase
            </label>
            <div className="flex gap-2">
              <Combobox
                id="add"
                className="w-48"
                options={characters.filter((c) => !queued.has(c.key) && !owned.has(c.key)).map((c) => ({ value: c.key, label: c.name }))}
                value={adding}
                onChange={setAdding}
                placeholder="Character"
                required
              />
              <button type="submit" className="btn-quiet">
                Queue
              </button>
            </div>
          </form>
          {rows.length > 0 && (
            <button onClick={clearAll} className="btn-quiet hover:border-bad hover:text-bad">
              Clear all
            </button>
          )}
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="font-display text-xl text-ink-2">Import your showcase or queue a character to get started.</p>
      ) : (
        <div>
          <div className={`${ROW} label hidden border-b border-rule-strong pb-2 md:grid`}>
            <span>Character</span>
            <span className="text-right">Equipped</span>
            <span>Slots</span>
            <span>Queue</span>
            <span />
          </div>
          <ul>
            {rows.map((r) => {
              const p = r.profile
              const q = r.queued
              const expanded = open === r.key
              const index = queue.findIndex((x) => x.character_key === r.key)
              return (
                <li key={r.key} className="border-b border-rule">
                  <div className={`${ROW} py-4`}>
                    <button onClick={() => setOpen(expanded ? null : r.key)} className="text-left">
                      <span className="font-display text-xl">{r.name}</span>
                      <span className="block text-xs text-ink-3">
                        {p ? `Lv. ${p.level} · ` : ''}
                        {buildLabel(q?.build ?? p?.build ?? '')}
                      </span>
                    </button>
                    <span
                      className={`num text-right text-2xl ${p ? tone(p.score) : 'text-ink-3'}`}
                      title={p ? SCORE_KIND[p.score_kind] : undefined}
                    >
                      {p ? p.score.toFixed(2) : '—'}
                    </span>
                    <div className="col-span-2 md:col-span-1">{p ? <Slots p={p} /> : <span className="text-xs text-ink-3">not in your showcase</span>}</div>
                    {q ? (
                      <div>
                        <p className="num mb-1 text-[11px] text-ink-3">#{q.priority}</p>
                        <Progress current={q.current} target={q.target_score} />
                      </div>
                    ) : (
                      <button onClick={() => enqueue(r.key, p?.build_id)} className="link justify-self-start text-sm">
                        Queue
                      </button>
                    )}
                    <div className="flex justify-end gap-4 text-sm">
                      <button onClick={() => setOpen(expanded ? null : r.key)} className="link">
                        {expanded ? 'Close' : 'Details'}
                      </button>
                      <button onClick={() => onStartSession(r.key)} className="link">
                        Farm
                      </button>
                    </div>
                  </div>
                  {expanded && (
                    <Details
                      row={r}
                      index={index}
                      count={queue.length}
                      onSave={(patch) => save(q!, patch)}
                      onMove={(dir) => move(index, dir)}
                      onRemove={() => dequeue(r.key)}
                    />
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
