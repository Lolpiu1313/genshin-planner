import type { BuildScore, Scores } from '../api/client'
import { buildLabel } from '../stats'

function tone(value: number) {
  if (value >= 50) return 'text-good'
  if (value >= 30) return 'text-warn'
  return 'text-ink-2'
}

function Headline({ label, s }: { label: string; s: BuildScore }) {
  return (
    <div>
      <p className="label">{label}</p>
      <p className="mt-1 font-display text-2xl">
        {s.character} <span className="text-base text-ink-3 italic">{buildLabel(s.build)}</span>
      </p>
      <p className="num mt-1 text-sm text-ink-2">
        <span className={`text-3xl ${tone(s.potential)}`}>{s.potential}</span> at max · {s.score} now
      </p>
    </div>
  )
}

export default function ScorePanel({ scores }: { scores: Scores | null }) {
  if (!scores?.overall) {
    return <p className="font-display text-xl text-ink-3 md:pt-8">Fill in a piece, or pick one from your inventory, to see who it suits.</p>
  }
  const { overall, top, character } = scores
  if (character) {
    return (
      <div className="md:border-l md:border-rule md:pl-10">
        <Headline label="For your pick" s={character} />
      </div>
    )
  }

  return (
    <div className="space-y-8 md:border-l md:border-rule md:pl-10">
      <Headline label="Best on" s={overall} />

      <div>
        <p className="label mb-2">Next best</p>
        <ul className="space-y-2">
          {top.map((s) => (
            <li key={s.character_key} className="grid grid-cols-[1fr_6rem_2.5rem] items-center gap-3 text-sm">
              <span className="truncate">
                {s.character} <span className="text-ink-3">{buildLabel(s.build)}</span>
              </span>
              <span className="h-[3px] bg-rule">
                <span className="block h-full bg-mark" style={{ width: `${s.potential}%` }} />
              </span>
              <span className="num text-right text-ink-2">{s.potential}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
