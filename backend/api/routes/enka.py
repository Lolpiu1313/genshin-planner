import json
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select

from api.deps import DbSession
from api.schemas import BuildOut, EnkaImportOut, EquippedPiece, ProfileCharacter
from api.scores import equipped_on, equipped_score, load_builds, pick_build, piece_scores, to_core, weights_source
from core.constants import SLOTS
from core.enka import parse
from db.models import Artifact, ArtifactSet, ArtifactSubstat, BuildQueue, Character, OwnedCharacter

router = APIRouter()

ENKA_URL = "https://enka.network/api/uid/{uid}/"
USER_AGENT = "genshin-planner/0.1"
ENKA_ERRORS = {
    400: (422, "invalid UID"),
    404: (404, "no player with this UID"),
    424: (503, "the game is under maintenance, try again later"),
    429: (503, "Enka rate limit hit, try again in a minute"),
}


def fetch_enka(uid: int) -> dict:
    req = urllib.request.Request(ENKA_URL.format(uid=uid), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        status, message = ENKA_ERRORS.get(e.code, (503, "Enka is unavailable"))
        raise HTTPException(status, message) from None
    except urllib.error.URLError:
        raise HTTPException(503, "could not reach Enka") from None


@router.post("/enka/{uid}", response_model=EnkaImportOut)
def import_enka(session: DbSession, uid: int):
    """Replace the previous Enka import with the characters in the player's showcase."""
    profile = parse(fetch_enka(uid))
    if not profile.characters:
        raise HTTPException(422, "the showcase is empty or hidden; add characters to it in game")

    chars = {c.game_id: c for c in session.scalars(select(Character).where(Character.game_id.is_not(None)))}
    sets = {s.game_id: s for s in session.scalars(select(ArtifactSet).where(ArtifactSet.game_id.is_not(None)))}
    session.execute(delete(Artifact).where(Artifact.source == "enka"))
    shown = [chars[c.avatar_id].id for c in profile.characters if c.avatar_id in chars]
    session.execute(delete(OwnedCharacter).where(OwnedCharacter.character_id.not_in(shown)))

    names, count, skipped = [], 0, 0
    for c in profile.characters:
        char = chars.get(c.avatar_id)
        if char is None:
            # e.g. the Traveler, which the game data lists without a fixed element
            skipped += 1
            continue
        owned = session.get(OwnedCharacter, char.id) or OwnedCharacter(character_id=char.id)
        owned.level, owned.stats = c.level, c.stats
        session.add(owned)
        for a in c.artifacts:
            if a.set_id not in sets or a.rarity < 3:
                continue
            session.add(Artifact(
                set=sets[a.set_id], slot=a.slot, main_stat=a.main_stat, level=a.level, rarity=a.rarity,
                source="enka", equipped_by=char.id,
                substats=[ArtifactSubstat(stat=k, value=v) for k, v in a.substats.items()],
            ))
            count += 1
        names.append(char.name)
    session.commit()
    return EnkaImportOut(nickname=profile.nickname, characters=names, artifacts=count, skipped=skipped)


@router.delete("/profile", status_code=204)
def clear_profile(session: DbSession):
    """Forget the imported characters, the artifacts they wear and the build queue."""
    session.execute(delete(Artifact).where(Artifact.source == "enka"))
    session.execute(delete(OwnedCharacter))
    session.execute(delete(BuildQueue))
    session.commit()


@router.get("/profile", response_model=list[ProfileCharacter])
def profile(session: DbSession):
    builds = load_builds(session)
    out = []
    for owned in session.scalars(select(OwnedCharacter).join(Character).order_by(Character.name)):
        char = owned.character
        worn = equipped_on(session, char.id)
        build, core = pick_build([bc for bc in builds if bc[0].character_id == char.id], worn)
        scores = piece_scores(worn, core)
        score, kind = equipped_score(build, core, owned.stats, {slot: to_core(a) for slot, a in worn.items()})
        out.append(ProfileCharacter(
            character_key=char.key,
            character=char.name,
            element=char.element,
            level=owned.level,
            build_id=build.id,
            build=build.name,
            builds=[BuildOut.model_validate(b) for b in char.builds],
            score=score,
            score_kind=kind,
            slots={s: EquippedPiece(set_key=worn[s].set.key, main_stat=worn[s].main_stat, level=worn[s].level,
                                    score=round(scores[s], 1)) if s in worn else None for s in SLOTS},
            stats=owned.stats,
            weights=core.weights,
            weights_source=weights_source(build, True),
        ))
    return out
