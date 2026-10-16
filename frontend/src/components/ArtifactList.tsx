import type { Artifact } from '../api/client'
import { SLOT_LABELS, formatStat, statLabel, type Slot } from '../stats'

const SHOWN = 30
const SOURCE: Record<string, string> = { enka: 'worn', good: 'GOOD', manual: '' }

type Props = {
  artifacts: Artifact[]
  setNames: Map<string, string>
  characterNames: Map<string, string>
  selected: number | null
  onSelect: (a: Artifact) => void
  onDelete: (a: Artifact) => void
}

export default function ArtifactList({ artifacts, setNames, characterNames, selected, onSelect, onDelete }: Props) {
  if (artifacts.length === 0) {
    return <p className="text-sm text-ink-3">Nothing here yet.</p>
  }
  return (
    <div>
      <ul>
        {artifacts.slice(0, SHOWN).map((a) => (
          <li
            key={a.id}
            onClick={() => onSelect(a)}
            className={`grid cursor-pointer grid-cols-[1fr_auto] items-baseline gap-x-6 gap-y-1 border-t border-rule py-3 md:grid-cols-[14rem_9rem_1fr_7rem_auto] ${
              selected === a.id ? 'bg-sheet' : 'hover:bg-sheet'
            }`}
          >
            <span className="truncate text-sm">{setNames.get(a.set_key) ?? a.set_key}</span>
            <span className="text-sm text-ink-2">
              {SLOT_LABELS[a.slot as Slot]} <span className="num text-ink-3">+{a.level}</span>
            </span>
            <span className="num col-span-2 truncate text-xs text-ink-2 md:col-span-1">
              <span className="text-ink">{statLabel(a.main_stat)}</span> · {a.substats.map(formatStat).join(' · ')}
              {a.unactivated.length > 0 && <span className="text-ink-3"> · {a.unactivated.map(formatStat).join(' · ')} (inactive)</span>}
            </span>
            <span className="hidden truncate text-xs text-ink-3 md:block">
              {a.equipped_by ? (characterNames.get(a.equipped_by) ?? a.equipped_by) : (SOURCE[a.source] ?? a.source)}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDelete(a)
              }}
              className="hidden text-xs text-ink-3 hover:text-bad md:block"
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
      {artifacts.length > SHOWN && <p className="mt-3 text-xs text-ink-3">Latest {SHOWN} of {artifacts.length}.</p>}
    </div>
  )
}
