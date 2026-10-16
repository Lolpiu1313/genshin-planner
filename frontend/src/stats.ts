export const SLOTS = ['flower', 'plume', 'sands', 'goblet', 'circlet'] as const
export type Slot = (typeof SLOTS)[number]

export const SLOT_LABELS: Record<Slot, string> = {
  flower: 'Flower',
  plume: 'Plume',
  sands: 'Sands',
  goblet: 'Goblet',
  circlet: 'Circlet',
}

const ELEMENTS = ['pyro', 'hydro', 'electro', 'cryo', 'anemo', 'geo', 'dendro', 'physical']

export const MAIN_STATS: Record<Slot, string[]> = {
  flower: ['hp'],
  plume: ['atk'],
  sands: ['atk_', 'hp_', 'def_', 'eleMas', 'enerRech_'],
  goblet: [...ELEMENTS.map((e) => `${e}_dmg_`), 'atk_', 'hp_', 'def_', 'eleMas'],
  circlet: ['critRate_', 'critDMG_', 'atk_', 'hp_', 'def_', 'eleMas', 'heal_'],
}

export const SUBSTATS = ['critRate_', 'critDMG_', 'atk_', 'hp_', 'def_', 'eleMas', 'enerRech_', 'atk', 'hp', 'def']

const LABELS: Record<string, string> = {
  hp: 'HP',
  hp_: 'HP%',
  atk: 'ATK',
  atk_: 'ATK%',
  def: 'DEF',
  def_: 'DEF%',
  eleMas: 'Elemental Mastery',
  enerRech_: 'Energy Recharge',
  critRate_: 'CRIT Rate',
  critDMG_: 'CRIT DMG',
  heal_: 'Healing Bonus',
}

export function statLabel(key: string): string {
  if (key.endsWith('_dmg_')) {
    const el = key.replace('_dmg_', '')
    return `${el[0].toUpperCase()}${el.slice(1)} DMG`
  }
  return LABELS[key] ?? key
}

export const isPercent = (key: string) => key.endsWith('_')

// build scores are averages of 0-100 piece scores; shown as a share of a perfect build
export const ratio = (score: number) => (score / 100).toFixed(2)

// rounded the way the game shows them: one decimal for percentages, whole numbers otherwise
export const formatStat = (s: { key: string; value: number }) =>
  `${statLabel(s.key).replace('%', '')} +${isPercent(s.key) ? `${s.value.toFixed(1)}%` : Math.round(s.value)}`

// a stat value as the game shows it, without the % sign
export const shownValue = (key: string, value: number) => (isPercent(key) ? value.toFixed(1) : String(Math.round(value)))

const ACRONYMS = new Set(['dps', 'em', 'er', 'hp', 'atk', 'def', 'c2', 'c4+', 'c6'])

/** Build names come in all caps; keep the acronyms and sentence-case the rest. */
export function buildLabel(name: string): string {
  const words = name.toLowerCase().split(' ').map((w) => (ACRONYMS.has(w.replace(/[()[\]]/g, '')) ? w.toUpperCase() : w))
  const text = words.join(' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export const nextCheck = (level: number, max: number) => Math.min(Math.floor(level / 4) * 4 + 4, max)
