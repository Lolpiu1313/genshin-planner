import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'

export type Option = { value: string; label: string; group?: string }

type Props = {
  options: Option[]
  value: string
  onChange: (value: string) => void
  placeholder?: string
  required?: boolean
  className?: string
  'aria-label'?: string
  id?: string
}

// typed text matches the start of any word first, then anywhere in the label
function rank(label: string, query: string) {
  const l = label.toLowerCase()
  if (l.startsWith(query)) return 0
  if (l.split(/[\s'-]+/).some((w) => w.startsWith(query))) return 1
  return l.includes(query) ? 2 : -1
}

export default function Combobox({ options, value, onChange, placeholder, required, className = '', id, ...rest }: Props) {
  const [query, setQuery] = useState<string | null>(null)
  const [active, setActive] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  const listId = useId()

  const selected = options.find((o) => o.value === value)
  const open = query !== null
  const q = query?.trim().toLowerCase() ?? ''
  const shown = q
    ? options
        .map((o) => ({ o, r: rank(o.label, q) }))
        .filter((x) => x.r >= 0)
        .sort((a, b) => a.r - b.r)
        .map((x) => x.o)
    : options

  useEffect(() => {
    if (open) document.getElementById(`${listId}-${active}`)?.scrollIntoView({ block: 'nearest' })
  }, [open, active, listId])

  function pick(o: Option) {
    onChange(o.value)
    setQuery(null)
    input.current?.blur()
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      if (!open) setQuery('')
      const step = e.key === 'ArrowDown' ? 1 : -1
      setActive((a) => Math.max(0, Math.min(shown.length - 1, a + step)))
    } else if (e.key === 'Enter' && open) {
      e.preventDefault()
      if (shown[active]) pick(shown[active])
    } else if (e.key === 'Escape') {
      setQuery(null)
    }
  }

  return (
    <div className={`relative ${className}`}>
      <input
        ref={input}
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-label={rest['aria-label']}
        className="field w-full min-w-0"
        value={open ? query : (selected?.label ?? '')}
        placeholder={selected?.label || placeholder}
        required={required && !selected?.value}
        onFocus={(e) => {
          setQuery('')
          setActive(Math.max(0, options.indexOf(selected!)))
          e.currentTarget.select()
        }}
        onChange={(e) => {
          setQuery(e.target.value)
          setActive(0)
        }}
        onBlur={() => setQuery(null)}
        onKeyDown={onKey}
        autoComplete="off"
      />
      {open && (
        <ul id={listId} role="listbox" className="absolute z-20 mt-1 max-h-72 w-full min-w-48 overflow-auto rounded-[3px] border border-rule-strong bg-sheet py-1 text-sm shadow-lg">
          {shown.length === 0 && <li className="px-2.5 py-1.5 text-ink-3">No match</li>}
          {shown.map((o, i) => (
            <li key={o.value} role="option" aria-selected={o.value === value}>
              {!q && o.group && o.group !== shown[i - 1]?.group && <p className="label px-2.5 pt-2 pb-1">{o.group}</p>}
              <button
                id={`${listId}-${i}`}
                type="button"
                tabIndex={-1}
                // mousedown fires before the input's blur closes the list
                onMouseDown={(e) => {
                  e.preventDefault()
                  pick(o)
                }}
                onMouseEnter={() => setActive(i)}
                className={`block w-full px-2.5 py-1.5 text-left ${i === active ? 'bg-rule' : ''} ${o.value === value ? 'text-ink' : 'text-ink-2'}`}
              >
                {o.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
