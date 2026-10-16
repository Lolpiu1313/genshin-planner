import { useRef, useState, type ChangeEvent } from 'react'
import { importGood } from '../api/client'

export default function ImportButton({ onDone }: { onDone: () => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [message, setMessage] = useState<string | null>(null)

  async function handle(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    try {
      const result = await importGood(JSON.parse(await file.text()))
      setMessage(`Imported ${result.imported}, skipped ${result.skipped}`)
      onDone()
    } catch (err) {
      setMessage(err instanceof SyntaxError ? 'Not a valid JSON file' : (err as Error).message)
    }
  }

  return (
    <div className="flex items-center gap-3">
      {message && <span className="text-xs text-ink-2">{message}</span>}
      <button onClick={() => input.current?.click()} className="btn-quiet">
        Import GOOD file
      </button>
      <input ref={input} type="file" accept=".json,application/json" className="hidden" onChange={handle} />
    </div>
  )
}
