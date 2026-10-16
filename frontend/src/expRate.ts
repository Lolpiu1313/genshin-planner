import { useEffect, useState } from 'react'

// EXP one point of piece score is worth to the player; the upgrade advice trades the two off
export const EXP_RATES = [
  { value: 5000, label: 'scarce' },
  { value: 10000, label: 'normal' },
  { value: 20000, label: 'plentiful' },
]
const DEFAULT = 10000
const KEY = 'exp-per-point'
const EVENT = 'exp-rate'

function stored() {
  try {
    return Number(localStorage.getItem(KEY)) || DEFAULT
  } catch {
    return DEFAULT
  }
}

export function useExpRate(): [number, (rate: number) => void] {
  const [rate, setRate] = useState(stored)
  useEffect(() => {
    const sync = () => setRate(stored())
    window.addEventListener(EVENT, sync)
    return () => window.removeEventListener(EVENT, sync)
  }, [])
  const update = (value: number) => {
    try {
      localStorage.setItem(KEY, String(value))
    } catch {
      // private mode: keep it for this page only
    }
    setRate(value)
    window.dispatchEvent(new Event(EVENT))
  }
  return [rate, update]
}
