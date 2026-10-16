import { lazy, Suspense, useEffect, useState, type FormEvent } from 'react'
import { getEstimate, logResin, type Estimate } from '../api/client'
import { ratio } from '../stats'

// the chart library is large, so it only loads once an estimate is opened
const Histogram = lazy(() => import('./Histogram'))

const resin = (x: number) => Math.round(x).toLocaleString('en-US')
const days = (x: number | null) => (x === null ? '—' : x < 1 ? 'under a day' : `${Math.round(x)} days`)

function luckText(p: number) {
  if (p >= 75) return 'luckier than most'
  if (p >= 40) return 'about average'
  return 'unlucky so far'
}

type Props = { character: string; buildId?: number; target: number }

export default function CharacterEstimate({ character, buildId, target: initialTarget }: Props) {
  const [target, setTarget] = useState(initialTarget)
  const [estimate, setEstimate] = useState<Estimate | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [runs, setRuns] = useState(1)
  const [condensed, setCondensed] = useState(false)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    // wait for the slider to settle before running a new simulation
    const timer = setTimeout(() => {
      setLoading(true)
      getEstimate(character, target, buildId)
        .then((e) => {
          setEstimate(e)
          setError(null)
        })
        .catch((e: Error) => setError(e.message))
        .finally(() => setLoading(false))
    }, 250)
    return () => clearTimeout(timer)
  }, [character, buildId, target, version])

  async function submitResin(e: FormEvent) {
    e.preventDefault()
    if (!estimate) return
    await logResin(estimate.domain.key, runs, condensed)
    setRuns(1)
    setVersion((v) => v + 1)
  }

  return (
    <div className="space-y-6">
      <label className="flex flex-wrap items-center gap-3 text-sm">
        <span className="text-ink-2">Aim for</span>
        <input
          type="range"
          min={25}
          max={65}
          value={target}
          onChange={(e) => setTarget(Number(e.target.value))}
          className="w-44 accent-[var(--color-ink)]"
          aria-label="Target build score"
        />
        <span className="num">{ratio(target)}</span>
        {loading && <span className="text-xs text-ink-3">simulating</span>}
      </label>

      {error && <p className="error">{error}</p>}

      {estimate && (
        <>
          <div>
            {estimate.resin.median === 0 ? (
              <p className="font-display text-2xl text-good">Already there.</p>
            ) : (
              <>
                <p className="font-display text-3xl">
                  About {days(estimate.days.median)}
                  {estimate.resin.median !== null && <span className="num ml-3 text-base text-ink-2">{resin(estimate.resin.median)} resin</span>}
                </p>
                <p className="mt-1 text-sm text-ink-2">
                  Usually {days(estimate.days.p25)} to {days(estimate.days.p75)}, rarely past {days(estimate.days.p90)}, farming{' '}
                  {estimate.domain.name} from your current {ratio(estimate.current)}.
                  {estimate.reached < 0.9 &&
                    ` Only ${Math.round(estimate.reached * 100)}% of simulations make it within ${resin(estimate.max_resin)} resin.`}
                </p>
              </>
            )}
            {estimate.histogram.length > 0 && (
              <div className="mt-3">
                <Suspense fallback={<div className="h-[200px]" />}>
                  <Histogram bins={estimate.histogram} marker={estimate.resin.median} markerLabel="median" format={resin} label="resin" />
                </Suspense>
              </div>
            )}
          </div>

          <div className="border-t border-rule pt-5">
            {estimate.luck ? (
              <>
                <p className="text-sm text-ink-2">
                  Against players who spent the same <span className="num">{resin(estimate.luck.resin_spent)}</span> resin here, you are{' '}
                  <span className="text-ink">{luckText(estimate.luck.percentile)}</span>{' '}
                  <span className="num">({estimate.luck.percentile}th percentile)</span>.
                </p>
                <Suspense fallback={<div className="h-[200px]" />}>
                  <Histogram bins={estimate.luck.histogram} marker={estimate.current} markerLabel="you" format={(x) => ratio(x)} label="build score" />
                </Suspense>
              </>
            ) : (
              <p className="text-sm text-ink-3">Log runs in {estimate.domain.name} to see how your luck compares.</p>
            )}

            <form onSubmit={submitResin} className="mt-3 flex flex-wrap items-center gap-2 text-sm">
              <span className="text-ink-2">Ran it</span>
              <input
                type="number"
                min={1}
                value={runs}
                onChange={(e) => setRuns(Math.max(1, Number(e.target.value)))}
                className="field num w-16"
                aria-label="Runs"
              />
              <span className="text-ink-2">times</span>
              <label className="ml-2 flex items-center gap-2 text-ink-2">
                <input type="checkbox" checked={condensed} onChange={(e) => setCondensed(e.target.checked)} className="accent-ink" />
                condensed
              </label>
              <button type="submit" className="btn-quiet ml-2">
                Log
              </button>
            </form>
          </div>
        </>
      )}
    </div>
  )
}
