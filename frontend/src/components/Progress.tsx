import { ratio } from '../stats'

export default function Progress({ current, target }: { current: number; target: number }) {
  const done = current >= target
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-[3px] flex-1 bg-rule">
        <div className={`h-full ${done ? 'bg-good' : 'bg-mark'}`} style={{ width: `${Math.min((current / target) * 100, 100)}%` }} />
      </div>
      <span className={`num text-xs ${done ? 'text-good' : 'text-ink-2'}`}>
        {ratio(current)}/{ratio(target)}
      </span>
    </div>
  )
}
