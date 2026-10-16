import { useState } from 'react'
import { startSession } from '../api/client'
import Recommendation from '../components/Recommendation'
import SessionPanel from '../components/SessionPanel'

type Props = { initialCharacter: string; onGoToCharacters: () => void }

export default function Farm({ initialCharacter, onGoToCharacters }: Props) {
  const [active, setActive] = useState(false)
  const [version, setVersion] = useState(0)

  async function start(character: string, domain: string) {
    await startSession(character, undefined, domain)
    // remount the panel so it picks up the session that just started
    setVersion((v) => v + 1)
  }

  return (
    <div className="space-y-10">
      <Recommendation canStart={!active} onStart={start} onEmpty={onGoToCharacters} />
      <SessionPanel key={version} initialCharacter={initialCharacter} initialDomain="" onActiveChange={setActive} />
    </div>
  )
}
