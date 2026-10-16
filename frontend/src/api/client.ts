export type Substat = { key: string; value: number }

export type Character = {
  id: number
  key: string
  name: string
  element: string
  weapon_type: string
  builds: { id: number; name: string; sets: string[] }[]
}

export type ArtifactSet = { key: string; name: string }

export type ArtifactInput = {
  set_key: string
  slot: string
  main_stat: string
  level: number
  rarity: number
  substats: Substat[]
  unactivated: Substat[]
}

export type Artifact = ArtifactInput & { id: number; source: string; equipped_by: string | null; obtained_at: string }

export type BuildScore = {
  character_key: string
  character: string
  build: string
  score: number
  potential: number
}

export type Scores = { overall: BuildScore | null; top: BuildScore[]; character: BuildScore | null }

export type ScoredArtifact = Artifact & { scores: Scores }

export type Quantiles = { p25: number | null; median: number | null; p75: number | null; p90: number | null }

export type Bin = { x: number; count: number }

export type Estimate = {
  character: string
  build: string
  domain: { id: number; key: string; name: string; sets: ArtifactSet[] }
  target: number
  current: number
  slots: Record<string, number>
  resin: Quantiles
  days: Quantiles
  reached: number
  max_resin: number
  histogram: Bin[]
  luck: { resin_spent: number; percentile: number; histogram: Bin[] } | null
}

export type WeightsSource = 'enka' | 'reference' | 'site'

export type QueueItem = {
  character_key: string
  character: string
  build_id: number
  build: string
  builds: { id: number; name: string }[]
  priority: number
  target_score: number
  current: number
  slots: Record<string, number>
  weights: Record<string, number>
  weights_source: WeightsSource
}

export type QueueUpdate = { character_key: string; build_id?: number; priority?: number; target_score: number }

export type Recommendation = {
  domain: { id: number; key: string; name: string; sets: ArtifactSet[] }
  value: number
  condensed: boolean
  stay_share: number
  focus: string | null
  close: boolean
  gains: { character_key: string; character: string; priority: number; gain: number }[]
  alternatives: { key: string; name: string; value: number }[]
}

export type EquippedPiece = { set_key: string; main_stat: string; level: number; score: number }

export type ProfileCharacter = {
  character_key: string
  character: string
  element: string
  level: number
  build_id: number
  build: string
  builds: { id: number; name: string }[]
  score: number
  score_kind: 'damage' | 'pieces'
  slots: Record<string, EquippedPiece | null>
  stats: Record<string, number>
  weights: Record<string, number>
  weights_source: WeightsSource
}

export type Domain = { id: number; key: string; name: string; sets: ArtifactSet[] }

export type Run = { id: number; domain_key: string; domain: string; resin: number; five_stars: number; date: string }

export type FarmSession = {
  id: number
  character_key: string
  character: string
  build_id: number
  build: string
  domain: Domain
  started_at: string
  ended_at: string | null
  runs: Run[]
  resin: number
  five_stars: number
  artifacts: Artifact[]
}

export type Advice = {
  character_key: string
  character: string
  build: string
  action: 'upgrade' | 'step' | 'skip' | 'done'
  stop: number | null
  level: number
  max_level: number
  score: number
  potential: number
  beat_chance: number
  expected_gain: number
  value: number
  reach_max: number
  keep_after_next: number
  success: number
  exp_next: number
  exp_expected: number
  next_rolls: { stat: string; chance: number; keep: number }[]
  equipped: EquippedPiece | null
  build_score: number | null
  build_score_with: number | null
  build_score_potential: number | null
  dmg_gain: number | null
  best: BuildScore | null
}

export const OFFLINE = 'Cannot reach the backend. Start uvicorn on port 8000.'

function errorMessage(body: unknown): string | null {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => String(d.msg).replace(/^Value error, /, '')).join('; ')
  return null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(errorMessage(body) ?? res.statusText)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

const query = (character: string) => (character ? `?character=${character}` : '')

export const getCharacters = () => request<Character[]>('/characters')
export const getSets = () => request<ArtifactSet[]>('/sets')

export type Rolls = Record<string, Record<string, number[]>>
let rolls: Promise<Rolls> | null = null
// fixed game data, so fetched once per page load
export const getRolls = () => (rolls ??= request<Rolls>('/rolls'))
export const getArtifacts = () => request<Artifact[]>('/artifacts')

export const addArtifact = (artifact: ArtifactInput, character: string) =>
  request<ScoredArtifact>(`/artifacts${query(character)}`, { method: 'POST', body: JSON.stringify(artifact) })

export const getScore = (id: number, character: string) => request<Scores>(`/artifacts/${id}/score${query(character)}`)

export const deleteArtifact = (id: number) => request<void>(`/artifacts/${id}`, { method: 'DELETE' })

export const getEstimate = (character: string, target: number, buildId?: number) => {
  const params = new URLSearchParams({ target: String(target) })
  if (buildId) params.set('build_id', String(buildId))
  return request<Estimate>(`/planner/estimate/${character}?${params}`)
}

export const logResin = (domainKey: string, runs: number, condensed: boolean) =>
  request<unknown>('/resin', { method: 'POST', body: JSON.stringify({ domain_key: domainKey, runs, condensed }) })

export const getQueue = () => request<QueueItem[]>('/queue')

export const saveQueue = (entry: QueueUpdate) =>
  request<void>('/queue', { method: 'POST', body: JSON.stringify(entry) })

export const removeQueue = (character: string) => request<void>(`/queue/${character}`, { method: 'DELETE' })

export const getRecommendation = () => request<Recommendation | null>('/planner/recommendation')

export const getDomains = () => request<Domain[]>('/domains')

export const importEnka = (uid: string) =>
  request<{ nickname: string; characters: string[]; artifacts: number; skipped: number }>(`/enka/${uid}`, { method: 'POST' })

export const getProfile = () => request<ProfileCharacter[]>('/profile')

export const clearProfile = () => request<void>('/profile', { method: 'DELETE' })

export const getActiveSession = () => request<FarmSession | null>('/sessions/active')

export const startSession = (character: string, buildId?: number, domainKey?: string) =>
  request<FarmSession>('/sessions', {
    method: 'POST',
    body: JSON.stringify({ character_key: character, build_id: buildId, domain_key: domainKey || undefined }),
  })

export const addRun = (sessionId: number, resin: number, fiveStars: number, domainKey?: string) =>
  request<FarmSession>(`/sessions/${sessionId}/runs`, {
    method: 'POST',
    body: JSON.stringify({ resin, five_stars: fiveStars, domain_key: domainKey || undefined }),
  })

export const endSession = (sessionId: number) => request<FarmSession>(`/sessions/${sessionId}/end`, { method: 'POST' })

export const addSessionArtifact = (artifact: ArtifactInput, sessionId: number) =>
  request<ScoredArtifact>(`/artifacts?session_id=${sessionId}`, { method: 'POST', body: JSON.stringify(artifact) })

export const updateArtifact = (id: number, artifact: ArtifactInput) =>
  request<Artifact>(`/artifacts/${id}`, { method: 'PUT', body: JSON.stringify(artifact) })

export const getAdvice = (id: number, character: string, expPerPoint: number) => {
  const params = new URLSearchParams({ exp_per_point: String(expPerPoint) })
  if (character) params.set('character', character)
  return request<Advice>(`/artifacts/${id}/advice?${params}`)
}

export const importGood = (good: unknown) =>
  request<{ imported: number; skipped: number }>('/artifacts/import', { method: 'POST', body: JSON.stringify(good) })
