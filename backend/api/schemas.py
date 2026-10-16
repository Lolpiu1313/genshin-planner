from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.constants import MAIN_STATS, MAX_LEVEL, SUBSTATS

Slot = Literal["flower", "plume", "sands", "goblet", "circlet"]


class BuildOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sets: list[str] = []  # recommended set keys, best first

    @field_validator("sets", mode="before")
    @classmethod
    def set_keys(cls, v: list) -> list[str]:
        return [s if isinstance(s, str) else s.set.key for s in v]


class CharacterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name: str
    element: str
    weapon_type: str
    builds: list[BuildOut]


class SetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str


class DomainOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name: str
    sets: list[SetOut]


class Substat(BaseModel):
    key: str
    value: float = Field(gt=0)


class ArtifactIn(BaseModel):
    set_key: str
    slot: Slot
    main_stat: str
    level: int = Field(0, ge=0)
    rarity: int = Field(5, ge=3, le=5)
    substats: list[Substat] = Field(max_length=4)
    unactivated: list[Substat] = Field([], max_length=1)

    @model_validator(mode="after")
    def check(self):
        if self.main_stat not in MAIN_STATS[self.slot]:
            raise ValueError(f"{self.main_stat} is not a valid {self.slot} main stat")
        if self.level > MAX_LEVEL[self.rarity]:
            raise ValueError(f"max level for {self.rarity}-star is {MAX_LEVEL[self.rarity]}")
        keys = [s.key for s in self.substats + self.unactivated]
        if len(keys) > 4:
            raise ValueError("at most 4 substats")
        if len(set(keys)) != len(keys) or self.main_stat in keys:
            raise ValueError("substats must be unique and differ from the main stat")
        if bad := set(keys) - set(SUBSTATS):
            raise ValueError(f"unknown substats: {', '.join(sorted(bad))}")
        return self


class ArtifactOut(BaseModel):
    id: int
    set_key: str
    slot: str
    main_stat: str
    level: int
    rarity: int
    substats: list[Substat]
    unactivated: list[Substat]
    source: str
    equipped_by: str | None = None  # key of the character wearing it
    obtained_at: datetime


class BuildScore(BaseModel):
    character_key: str
    character: str
    build: str
    score: float
    potential: float


class ScoreOut(BaseModel):
    overall: BuildScore | None
    top: list[BuildScore]
    character: BuildScore | None = None


class ScoredArtifact(ArtifactOut):
    scores: ScoreOut


class ImportResult(BaseModel):
    imported: int
    skipped: int


class Quantiles(BaseModel):
    p25: float | None
    median: float | None
    p75: float | None
    p90: float | None


class Bin(BaseModel):
    x: float
    count: int


class Luck(BaseModel):
    resin_spent: int
    percentile: float
    histogram: list[Bin]


class EstimateOut(BaseModel):
    character: str
    build: str
    domain: DomainOut
    target: float
    current: float
    slots: dict[str, float]
    resin: Quantiles
    days: Quantiles
    reached: float
    max_resin: int
    histogram: list[Bin]
    luck: Luck | None


class QueueIn(BaseModel):
    character_key: str
    build_id: int | None = None
    priority: int | None = Field(None, ge=1)
    target_score: float = Field(45, gt=0, le=100)


class QueueOut(BaseModel):
    character_key: str
    character: str
    build_id: int
    build: str
    builds: list[BuildOut]
    priority: int
    target_score: float
    current: float
    slots: dict[str, float]
    weights: dict[str, float]
    weights_source: str


class CharacterGain(BaseModel):
    character_key: str
    character: str
    priority: int
    gain: float


class DomainChoice(BaseModel):
    key: str
    name: str
    value: float


class RecommendationOut(BaseModel):
    domain: DomainOut
    value: float
    condensed: bool
    stay_share: float
    focus: str | None
    close: bool
    gains: list[CharacterGain]
    alternatives: list[DomainChoice]


class EnkaImportOut(BaseModel):
    nickname: str
    characters: list[str]
    artifacts: int
    skipped: int


class EquippedPiece(BaseModel):
    set_key: str
    main_stat: str
    level: int
    score: float


class ProfileCharacter(BaseModel):
    character_key: str
    character: str
    element: str
    level: int
    build_id: int
    build: str
    builds: list[BuildOut]
    score: float
    score_kind: str
    slots: dict[str, EquippedPiece | None]
    stats: dict[str, float]
    weights: dict[str, float]
    weights_source: str


class SessionIn(BaseModel):
    character_key: str
    build_id: int | None = None
    domain_key: str | None = None


class RunIn(BaseModel):
    domain_key: str | None = None
    resin: int = Field(20, ge=1)
    five_stars: int = Field(1, ge=0, le=10)


class RunOut(BaseModel):
    id: int
    domain_key: str
    domain: str
    resin: int
    five_stars: int
    date: datetime


class SessionOut(BaseModel):
    id: int
    character_key: str
    character: str
    build_id: int
    build: str
    domain: DomainOut
    started_at: datetime
    ended_at: datetime | None
    runs: list[RunOut]
    resin: int
    five_stars: int
    artifacts: list[ArtifactOut]


class NextRoll(BaseModel):
    stat: str
    chance: float
    keep: float


class AdviceOut(BaseModel):
    character_key: str
    character: str
    build: str
    action: str
    stop: int | None
    level: int
    max_level: int
    score: float
    potential: float
    beat_chance: float
    expected_gain: float
    value: float
    reach_max: float
    keep_after_next: float
    success: float
    exp_next: int
    exp_expected: float
    next_rolls: list[NextRoll]
    equipped: EquippedPiece | None
    build_score: float | None
    build_score_with: float | None
    build_score_potential: float | None
    dmg_gain: float | None
    best: BuildScore | None


class ResinIn(BaseModel):
    domain_key: str
    runs: int = Field(1, ge=1)
    condensed: bool = False


class ResinOut(BaseModel):
    id: int
    domain_key: str
    resin_spent: int
    condensed: bool
    date: datetime
