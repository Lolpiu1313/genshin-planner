import { useEffect, useState, type FormEvent } from 'react'
import { getRolls, type ArtifactInput, type ArtifactSet, type Rolls, type Substat } from '../api/client'
import { MAIN_STATS, SLOTS, SLOT_LABELS, SUBSTATS, isPercent, shownValue, statLabel, type Slot } from '../stats'
import Combobox, { type Option } from './Combobox'

type Row = { key: string; value: string }

// the initial roll closest to what was typed, as the game shows it
function snap(rows: Row[], values: Record<string, number[]> | undefined): Row[] {
  return rows.map((r) => {
    const options = values?.[r.key] ?? []
    if (!r.key || !r.value || options.length === 0) return r
    const best = options.reduce((a, b) => (Math.abs(b - Number(r.value)) < Math.abs(a - Number(r.value)) ? b : a))
    return { ...r, value: shownValue(r.key, best) }
  })
}

function toRows(a?: ArtifactInput): Row[] {
  const subs = a ? [...a.substats, ...a.unactivated] : []
  return Array.from({ length: 4 }, (_, i) => (subs[i] ? { key: subs[i].key, value: String(subs[i].value) } : { key: '', value: '' }))
}

type Props = {
  sets: ArtifactSet[]
  onSubmit: (artifact: ArtifactInput) => Promise<void>
  initial?: ArtifactInput
  submitLabel?: string
  // set keys to list first, e.g. the ones the character being built uses
  preferred?: { label: string; keys: string[] }
}

function setOptions(sets: ArtifactSet[], preferred?: Props['preferred']): Option[] {
  if (!preferred?.keys.length) return sets.map((s) => ({ value: s.key, label: s.name }))
  const byKey = new Map(sets.map((s) => [s.key, s]))
  const first = preferred.keys.filter((k) => byKey.has(k)).map((k) => ({ value: k, label: byKey.get(k)!.name, group: preferred.label }))
  const rest = sets.filter((s) => !preferred.keys.includes(s.key)).map((s) => ({ value: s.key, label: s.name, group: 'All sets' }))
  return [...first, ...rest]
}

export default function ArtifactForm({ sets, onSubmit, initial, submitLabel = 'Add and score', preferred }: Props) {
  // with only a domain's two sets to pick from, preselect the first
  const [setKey, setSetKey] = useState(initial?.set_key ?? (sets.length <= 2 ? (sets[0]?.key ?? '') : ''))
  const [slot, setSlot] = useState<Slot>((initial?.slot as Slot) ?? 'flower')
  const [mainStat, setMainStat] = useState(initial?.main_stat ?? 'hp')
  const [rarity, setRarity] = useState(initial?.rarity ?? 5)
  const [level, setLevel] = useState(initial?.level ?? 0)
  const [rows, setRows] = useState(() => toRows(initial))
  const [inactive, setInactive] = useState((initial?.unactivated.length ?? 0) > 0)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [rolls, setRolls] = useState<Rolls | null>(null)

  useEffect(() => {
    getRolls().then((r) => {
      setRolls(r)
      if ((initial?.level ?? 0) < 4) setRows((rows) => snap(rows, r[initial?.rarity ?? 5]))
    })
  }, [initial])

  // below +4 no line has been upgraded yet, so each value is one of the four initial rolls
  const fresh = level < 4 && rolls !== null
  const choices = (key: string) => (rolls?.[rarity]?.[key] ?? []).map((v) => shownValue(key, v))

  const maxLevel = rarity === 5 ? 20 : 16
  const hideLast = inactive && level < 4

  function changeSlot(s: Slot) {
    setSlot(s)
    setMainStat(MAIN_STATS[s][0])
    setRows(rows.map((r) => (r.key === MAIN_STATS[s][0] ? { ...r, key: '' } : r)))
  }

  function changeRarity(r: number) {
    setRarity(r)
    setLevel(Math.min(level, r === 5 ? 20 : 16))
    if (level < 4) setRows(snap(rows, rolls?.[r]))
  }

  function changeLevel(value: number) {
    setLevel(value)
    if (value < 4) setRows(snap(rows, rolls?.[rarity]))
  }

  function updateRow(i: number, patch: Partial<Row>) {
    // a new stat at +0 can't keep the old stat's value
    const reset = fresh && patch.key !== undefined ? { value: '' } : {}
    setRows(rows.map((r, j) => (j === i ? { ...r, ...reset, ...patch } : r)))
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    const parsed: Substat[] = rows.map((r) => ({ key: r.key, value: Number(r.value) }))
    const valid = (s: Substat) => s.key !== '' && s.value > 0
    setBusy(true)
    setError(null)
    try {
      await onSubmit({
        set_key: setKey,
        slot,
        main_stat: mainStat,
        level,
        rarity,
        substats: (hideLast ? parsed.slice(0, 3) : parsed).filter(valid),
        unactivated: hideLast ? parsed.slice(3).filter(valid) : [],
      })
      if (!initial) {
        setRows(toRows())
        setLevel(0)
        setInactive(false)
      }
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const choose = (active: boolean) =>
    `border-b-2 pb-1 text-sm ${active ? 'border-ink text-ink' : 'border-transparent text-ink-3 hover:text-ink'}`

  return (
    <form onSubmit={submit} className="space-y-5">
      {sets.length <= 2 ? (
        <div className="flex flex-wrap gap-5" role="radiogroup" aria-label="Set">
          {sets.map((s) => (
            <button key={s.key} type="button" role="radio" aria-checked={setKey === s.key} onClick={() => setSetKey(s.key)} className={choose(setKey === s.key)}>
              {s.name}
            </button>
          ))}
        </div>
      ) : (
        <Combobox options={setOptions(sets, preferred)} value={setKey} onChange={setSetKey} placeholder="Set" required aria-label="Set" />
      )}

      <div className="flex flex-wrap gap-5" role="radiogroup" aria-label="Slot">
        {SLOTS.map((s) => (
          <button key={s} type="button" role="radio" aria-checked={slot === s} onClick={() => changeSlot(s)} className={choose(slot === s)}>
            {SLOT_LABELS[s]}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_5rem_5rem] gap-3">
        <label>
          <span className="label">Main stat</span>
          <Combobox
            className="mt-1"
            options={MAIN_STATS[slot].map((m) => ({ value: m, label: statLabel(m) }))}
            value={mainStat}
            onChange={setMainStat}
            aria-label="Main stat"
          />
        </label>
        <label>
          <span className="label">Rarity</span>
          <select className="field num mt-1 w-full" value={rarity} onChange={(e) => changeRarity(Number(e.target.value))}>
            <option value={5}>5★</option>
            <option value={4}>4★</option>
          </select>
        </label>
        <label>
          <span className="label">Level</span>
          <input
            className="field num mt-1 w-full"
            type="number"
            min={0}
            max={maxLevel}
            value={level}
            onChange={(e) => changeLevel(Math.max(0, Math.min(maxLevel, Number(e.target.value))))}
          />
        </label>
      </div>

      <fieldset>
        <legend className="label">Substats</legend>
        <div className="mt-1 grid gap-2 sm:grid-cols-2">
          {rows.map((row, i) => {
            const taken = rows.filter((_, j) => j !== i).map((r) => r.key)
            const dim = i === 3 && hideLast
            return (
              <div key={i} className={`grid grid-cols-[minmax(0,1fr)_5.5rem] gap-2 ${dim ? 'opacity-50' : ''}`}>
                <Combobox
                  options={[
                    { value: '', label: '—' },
                    ...SUBSTATS.filter((s) => s !== mainStat && !taken.includes(s)).map((s) => ({ value: s, label: statLabel(s) })),
                  ]}
                  value={row.key}
                  onChange={(key) => updateRow(i, { key })}
                  aria-label={`Substat ${i + 1}`}
                />
                {fresh ? (
                  <select
                    className="field num min-w-0"
                    value={choices(row.key).includes(row.value) ? row.value : ''}
                    onChange={(e) => updateRow(i, { value: e.target.value })}
                    disabled={!row.key}
                    aria-label={`Substat ${i + 1} value`}
                  >
                    <option value="">—</option>
                    {choices(row.key).map((v) => (
                      <option key={v} value={v}>
                        {v}
                        {isPercent(row.key) ? '%' : ''}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    className="field num min-w-0"
                    type="number"
                    step="0.1"
                    min={0}
                    placeholder="0"
                    value={row.value}
                    onChange={(e) => updateRow(i, { value: e.target.value })}
                    aria-label={`Substat ${i + 1} value`}
                  />
                )}
              </div>
            )
          })}
        </div>
        {level < 4 && (
          <label className="mt-2 flex items-center gap-2 text-xs text-ink-2">
            <input type="checkbox" checked={inactive} onChange={(e) => setInactive(e.target.checked)} className="accent-ink" />
            The 4th line is greyed out (unlocks at +4)
          </label>
        )}
      </fieldset>

      {error && <p className="error">{error}</p>}

      <button type="submit" disabled={busy} className="btn">
        {busy ? 'Scoring...' : submitLabel}
      </button>
    </form>
  )
}
