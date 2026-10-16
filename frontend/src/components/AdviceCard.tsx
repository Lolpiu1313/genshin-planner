import type { Advice } from '../api/client'
import { EXP_RATES, useExpRate } from '../expRate'
import { buildLabel, statLabel } from '../stats'

const VERDICT: Record<Advice['action'], (a: Advice) => { text: string; tone: string }> = {
  upgrade: (a) => ({ text: `Level it to +${a.stop}.`, tone: 'text-good' }),
  step: (a) => ({ text: `Level it to +${a.stop}, then look again.`, tone: 'text-warn' }),
  skip: () => ({ text: 'Feed it to something else.', tone: 'text-ink-3' }),
  done: (a) => ({ text: a.beat_chance ? 'Maxed, and better than what you wear.' : 'Maxed. Keep what you wear.', tone: 'text-ink' }),
}

const pct = (x: number) => `${Math.round(x * 100)}%`
const ratio = (x: number | null) => (x === null ? '—' : x.toFixed(2))
const kexp = (x: number) => `${(x / 1000).toFixed(x < 10000 ? 1 : 0)}k`
const signed = (x: number) => `${x >= 0 ? '+' : '−'}${Math.abs(x * 100).toFixed(1)}%`

function Track({ level, max }: { level: number; max: number }) {
  const stops = Array.from({ length: max / 4 + 1 }, (_, i) => i * 4)
  const at = Math.floor(level / 4) * 4
  return (
    <ol className="num flex gap-3 text-[11px]" aria-label={`Level +${level} of +${max}`}>
      {stops.map((s) => (
        <li key={s} className={s === at ? 'border-b border-ink text-ink' : s < at ? 'text-ink-2' : 'text-ink-3/60'}>
          {s}
        </li>
      ))}
    </ol>
  )
}

function NextRolls({ advice }: { advice: Advice }) {
  const last = advice.level >= advice.max_level - 4
  const verdict = (keep: number) => {
    if (keep === 1) return { text: last ? 'ends better' : 'keep going', tone: 'text-good' }
    if (keep === 0) return { text: last ? 'ends worse' : 'stop there', tone: 'text-bad' }
    return { text: `${last ? 'ends better' : 'keep going'} on ${pct(keep)} of roll sizes`, tone: 'text-warn' }
  }
  return (
    <div>
      <p className="label mb-2">If the next +4 hits</p>
      <ul className="space-y-1 text-sm">
        {advice.next_rolls.map((r) => {
          const { text, tone } = verdict(r.keep)
          return (
            <li key={r.stat} className="grid grid-cols-[9rem_3rem_1fr] gap-3">
              <span>{statLabel(r.stat)}</span>
              <span className="num text-right text-ink-3">{pct(r.chance)}</span>
              <span className={tone}>{text}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function Fact({ label, value, tone = '' }: { label: string; value: string; tone?: string }) {
  return (
    <div>
      <dt className="label">{label}</dt>
      <dd className={`num mt-0.5 ${tone}`}>{value}</dd>
    </div>
  )
}

export default function AdviceCard({ advice }: { advice: Advice }) {
  const { text, tone } = VERDICT[advice.action](advice)
  const maxed = advice.action === 'done'
  const better = advice.best && advice.best.character_key !== advice.character_key && advice.best.potential > advice.potential
  const [rate, setRate] = useExpRate()
  const equipped = advice.equipped ? `${advice.equipped.score} · ${statLabel(advice.equipped.main_stat)}` : 'empty slot'

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <p className={`font-display text-xl ${tone}`}>{text}</p>
        <Track level={advice.level} max={advice.max_level} />
      </div>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-4">
        <Fact label="Score" value={maxed ? String(advice.score) : `${advice.score} → ${advice.potential}`} />
        <Fact label="Wearing" value={equipped} />
        <Fact label={maxed ? 'Beats it' : 'Odds to beat it'} value={maxed ? (advice.beat_chance ? 'yes' : 'no') : pct(advice.beat_chance)} />
        {advice.dmg_gain !== null && (
          <Fact label={maxed ? 'Damage' : 'Damage at this level'} value={signed(advice.dmg_gain)} tone={advice.dmg_gain >= 0 ? 'text-good' : 'text-bad'} />
        )}
      </dl>

      {(advice.action === 'upgrade' || advice.action === 'step') && advice.next_rolls.length > 0 && <NextRolls advice={advice} />}

      {better && advice.best && (
        <p className="text-sm text-ink-2">
          Better on <span className="text-ink">{advice.best.character}</span> ({buildLabel(advice.best.build)}), {advice.best.potential} at max.
        </p>
      )}

      {!maxed && (
        <details className="group text-sm">
          <summary className="cursor-pointer list-none text-xs text-ink-3 hover:text-ink">
            <span className="group-open:hidden">Odds, cost and build impact</span>
            <span className="hidden group-open:inline">Hide details</span>
          </summary>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 border-l border-rule pl-4 sm:grid-cols-3">
            <Fact label="Expected gain at max" value={`+${advice.expected_gain}`} />
            <Fact label="Still worth it after next +4" value={pct(advice.keep_after_next)} />
            <Fact label="Reaches max, following the advice" value={pct(advice.reach_max)} />
            <Fact label="Ends better, following the advice" value={pct(advice.success)} />
            <Fact label="EXP to next +4" value={kexp(advice.exp_next)} />
            <Fact label="EXP expected in total" value={kexp(advice.exp_expected)} />
            <Fact label="Worth, net of lost EXP" value={`${kexp(advice.value)} EXP`} />
            {advice.build_score !== null && (
              <Fact
                label="Build, out of 1"
                value={`${ratio(advice.build_score)} → ${ratio(advice.build_score_with)} now${
                  advice.build_score_potential === null ? '' : `, ~${ratio(advice.build_score_potential)} at max`
                }`}
              />
            )}
          </dl>
          <label className="mt-4 flex items-center gap-2 text-xs text-ink-3">
            EXP is
            <select value={rate} onChange={(e) => setRate(Number(e.target.value))} className="field py-0.5 text-xs">
              {EXP_RATES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label} ({kexp(r.value)} per point)
                </option>
              ))}
            </select>
          </label>
        </details>
      )}
    </div>
  )
}
