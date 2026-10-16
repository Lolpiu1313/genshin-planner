from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, MetaData, String, func, true
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    game_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(64))
    element: Mapped[str] = mapped_column(String(16))
    weapon_type: Mapped[str] = mapped_column(String(16))
    # level 90 base stats and the stat its ascension raises, in GOOD units
    base_hp: Mapped[float | None] = mapped_column(Float)
    base_atk: Mapped[float | None] = mapped_column(Float)
    base_def: Mapped[float | None] = mapped_column(Float)
    ascension_stat: Mapped[str | None] = mapped_column(String(32))
    ascension_value: Mapped[float | None] = mapped_column(Float)

    builds: Mapped[list["CharBuild"]] = relationship(back_populates="character", cascade="all, delete-orphan")
    scalings: Mapped[list["TalentScaling"]] = relationship(cascade="all, delete-orphan")


class TalentScaling(Base):
    """What a character's talent hits scale on, read from the game's talent labels."""

    __tablename__ = "talent_scalings"

    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True)
    talent: Mapped[str] = mapped_column(String(16), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    stat: Mapped[str] = mapped_column(String(32), primary_key=True)
    coef: Mapped[float] = mapped_column(Float)


class Domain(Base):
    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))

    sets: Mapped[list["ArtifactSet"]] = relationship(back_populates="domain")


class ArtifactSet(Base):
    __tablename__ = "artifact_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    game_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(128))
    domain_id: Mapped[int | None] = mapped_column(ForeignKey("domains.id"))

    domain: Mapped[Domain | None] = relationship(back_populates="sets")


class CharBuild(Base):
    __tablename__ = "char_builds"

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    sands_main: Mapped[list[str]] = mapped_column(JSON)
    goblet_main: Mapped[list[str]] = mapped_column(JSON)
    circlet_main: Mapped[list[str]] = mapped_column(JSON)
    talent_priority: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")

    character: Mapped[Character] = relationship(back_populates="builds")
    sets: Mapped[list["BuildSet"]] = relationship(order_by="BuildSet.rank", cascade="all, delete-orphan")
    weights: Mapped[list["StatWeight"]] = relationship(cascade="all, delete-orphan")


class BuildSet(Base):
    __tablename__ = "build_sets"

    build_id: Mapped[int] = mapped_column(ForeignKey("char_builds.id", ondelete="CASCADE"), primary_key=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("artifact_sets.id"), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer)

    set: Mapped[ArtifactSet] = relationship()


class StatWeight(Base):
    __tablename__ = "stat_weights"

    build_id: Mapped[int] = mapped_column(ForeignKey("char_builds.id", ondelete="CASCADE"), primary_key=True)
    stat: Mapped[str] = mapped_column(String(32), primary_key=True)
    weight: Mapped[float] = mapped_column(Float)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("artifact_sets.id"), index=True)
    slot: Mapped[str] = mapped_column(String(16))
    main_stat: Mapped[str] = mapped_column(String(32))
    level: Mapped[int] = mapped_column(Integer, default=0)
    rarity: Mapped[int] = mapped_column(Integer, default=5)
    obtained_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    source: Mapped[str] = mapped_column(String(16), default="manual", server_default="manual")
    equipped_by: Mapped[int | None] = mapped_column(ForeignKey("characters.id", ondelete="SET NULL"))
    session_id: Mapped[int | None] = mapped_column(ForeignKey("farm_sessions.id", ondelete="SET NULL"))

    set: Mapped[ArtifactSet] = relationship()
    substats: Mapped[list["ArtifactSubstat"]] = relationship(cascade="all, delete-orphan")
    wearer: Mapped[Character | None] = relationship()


class ArtifactSubstat(Base):
    __tablename__ = "artifact_substats"

    artifact_id: Mapped[int] = mapped_column(ForeignKey("artifacts.id", ondelete="CASCADE"), primary_key=True)
    stat: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())


class ResinLog(Base):
    __tablename__ = "resin_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id"))
    resin_spent: Mapped[int] = mapped_column(Integer)
    condensed: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    session_id: Mapped[int | None] = mapped_column(ForeignKey("farm_sessions.id", ondelete="SET NULL"))
    five_stars: Mapped[int | None] = mapped_column(Integer)

    domain: Mapped[Domain] = relationship()


class BuildQueue(Base):
    __tablename__ = "build_queue"

    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True)
    build_id: Mapped[int | None] = mapped_column(ForeignKey("char_builds.id", ondelete="SET NULL"))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    target_score: Mapped[float] = mapped_column(Float)

    character: Mapped[Character] = relationship()
    build: Mapped[CharBuild | None] = relationship()


class OwnedCharacter(Base):
    """A character from the player's Enka showcase, with its in-game stats."""

    __tablename__ = "owned_characters"

    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True)
    level: Mapped[int] = mapped_column(Integer)
    stats: Mapped[dict[str, float]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    character: Mapped[Character] = relationship()


class FarmSession(Base):
    __tablename__ = "farm_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"))
    build_id: Mapped[int | None] = mapped_column(ForeignKey("char_builds.id", ondelete="SET NULL"))
    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)

    character: Mapped[Character] = relationship()
    build: Mapped[CharBuild | None] = relationship()
    domain: Mapped[Domain] = relationship()
    runs: Mapped[list[ResinLog]] = relationship(order_by="ResinLog.id")
    artifacts: Mapped[list[Artifact]] = relationship(order_by="Artifact.id")
