import { useCallback, useEffect, useState } from 'react'
import { getRecommendation, type Recommendation as Rec } from '../api/client'

type Props = {
  onStart: (character: string, domain: string) => void
  canStart: boolean
  onEmpty: () => void
}

export default function Recommendation({ onStart, canStart, onEmpty }: Props) {
  const [rec, setRec] = useState<Rec | null | undefined>(undefined)
  const [loading, setLoading] = useState(false)

  const load = useCallback(() => getRecommendation().then(setRec).finally(() => setLoading(false)), [])

  useEffect(() => {
    load()
  }, [load])

  if (rec === undefined) return null
  if (rec === null) {
    return (
      <section className="border-b border-rule pb-10">
        <p className="label">Next run</p>
        <p className="mt-2 max-w-xl font-display text-2xl text-ink-2">
          Queue the characters you want to build and this is where the best domain for them shows up.
        </p>
        <button onClick={onEmpty} className="link mt-3 text-sm">
          Pick characters
        </button>
      </section>
    )
  }

  const focus = rec.gains.reduce((a, b) => (b.gain > a.gain ? b : a), rec.gains[0])

  if (rec.value === 0) {
    return (
      <section className="border-b border-rule pb-10">
        <p className="label">Next run</p>
        <p className="mt-2 font-display text-3xl">Everyone in the queue has hit their target.</p>
      </section>
    )
  }

  return (
    <section className="grid gap-8 border-b border-rule pb-10 md:grid-cols-[1fr_19rem]">
      <div>
        <div className="flex items-baseline gap-4">
          <p className="label">Next run</p>
          <button
            onClick={() => {
              setLoading(true)
              load()
            }}
            disabled={loading}
            className="text-[11px] text-ink-3 hover:text-ink disabled:opacity-50"
          >
            {loading ? 'recomputing' : 'recompute'}
          </button>
        </div>
        <h1 className="mt-1 font-display text-4xl leading-tight md:text-5xl">{rec.domain.name}</h1>
        <p className="mt-1 text-ink-2">{rec.domain.sets.map((s) => s.name).join(' · ')}</p>

        <p className="mt-5 max-w-xl text-sm leading-relaxed text-ink-2">
          {rec.condensed ? (
            <>
              <span className="font-medium text-ink">Use Condensed Resin.</span> This stays the best domain after the next run in{' '}
              <span className="num">{Math.round(rec.stay_share * 100)}%</span> of outcomes.
            </>
          ) : (
            <>
              <span className="font-medium text-ink">Run it one at a time.</span> The pick may change after the next drop.
            </>
          )}{' '}
          Mostly for <span className="font-medium text-ink">{rec.focus}</span>.
          {rec.close && rec.alternatives[0] && <> Nearly tied with {rec.alternatives[0].name}.</>}
        </p>

        {canStart && (
          <button onClick={() => onStart(focus.character_key, rec.domain.key)} className="btn mt-6">
            Start session for {focus.character}
          </button>
        )}
      </div>

      <div className="space-y-2 text-sm md:border-l md:border-rule md:pl-8">
        <p className="label">Value per run</p>
        <ul className="space-y-1.5">
          <li className="flex justify-between gap-3">
            <span className="truncate">{rec.domain.name}</span>
            <span className="num text-ink-2">100</span>
          </li>
          {rec.alternatives.map((a) => (
            <li key={a.key} className="flex justify-between gap-3 text-ink-2">
              <span className="truncate">{a.name}</span>
              <span className="num text-ink-3">{Math.round((a.value / rec.value) * 100)}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
