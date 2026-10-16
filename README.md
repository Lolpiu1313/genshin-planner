# Genshin Planner

A planner for farming artifacts in Genshin Impact. It is a web app, but the substance is the
probability underneath it. Farming artifacts is a stochastic process with well-documented odds,
and most of the decisions a player makes (which domain to run, whether to level a piece, when
a build is "done") can be framed as expected-value or stopping problems.

Most of it is exact calculation, with Monte Carlo used where the state space is too large and
to cross-check the exact results. There is no machine learning.

## What it answers

- **How good is this artifact for this character?** A 0–100 score now, and its exact expected
  score once levelled.
- **Should I level it?** The optimal stopping policy over its upgrades, given how much EXP a point
  of score is worth to you, re-evaluated after every +4. Also the exact odds that it ends up better
  than the piece you wear, and the EXP you can expect to spend.
- **How much DMG would it add?** A relative estimate from the character's real in-game stats,
  imported from their Enka.Network showcase.
- **How long until my build is done?** The distribution of resin and days needed to reach a
  target build score.
- **Am I unlucky?** Your build score as a percentile among simulated players who spent the
  same resin.
- **Which domain next, and condensed or not?** The domain with the highest expected gain per run
  across your queue of characters.

## The mathematics

### Data
Roll values, main stat values per level and the EXP curve come straight from the game's data
tables (`backend/data/Reliquary*.json`). Main stat odds and substat pick weights (6/4/3) match
Genshin Optimizer and the community wiki. Drop rates: 1.065 five-stars per domain run, and a 20%
chance of starting with four substats.

### Artifact score
For a build with substat weights $w_s$, an artifact's weighted roll value is

$$V = \sum_s w_s \frac{v_s}{r_s}$$

where $v_s$ is the substat's value and $r_s$ its maximum single roll. $V$ is compared with the
best value a +20 piece with the same main stat could reach: the four highest weights, plus five
upgrades into the best one. The ratio is then scaled by set and main stat fit
(`core/scoring.py`).

### Exact expected value after levelling
Every upgrade either adds a new substat (picked by weight, excluding those already present) or
adds a 70/80/90/100% roll to one of four existing substats, chosen uniformly. Expectation is
linear, so the expected value at +20 has a closed recursive form over the possible new substats,
with no sampling involved.

### Markov chain over upgrades
`core/markov.py` models levelling as a Markov chain. A state is (set of substats, weighted value
so far), and each +4 is one transition. Propagating it gives the **exact distribution** of the
final score, which yields:

- the probability of beating the equipped piece,
- the expected gain over it, counting a miss as zero,
- the expected score at max.

The chain is checked against a roll-by-roll simulation in the tests. Its expected value matches
the closed form to within 1e-4.

### Optimal stopping
Levelling is a Markov decision process on the same states. Before every +4 you either stop or pay
for the next roll. Feeding a levelled piece to another returns 80% of its EXP, so a +4 really
costs the other 20%. A maxed piece is worth $\lambda \max(S - S_{\text{equipped}}, 0)$, where
$\lambda$ is how much EXP one point of score is worth to the player. Backward induction from +20
gives, in every reachable state,

$$V_i(x) = \max\Big(0,\; -c_i + \sum_{x'} P(x' \mid x)\, V_{i+1}(x')\Big)$$

and the advice follows the maximising choice. "Level it to +20" when no outcome makes stopping
better, "level it to the next +4" when some do, "feed it" when stopping is better now. The same
policy gives the chance of reaching max, the chance of ending with a better piece, the expected EXP
spent and the expected net value. It also shows, for each substat the next +4 can hit, whether the
policy would carry on afterwards. After every +4 you enter the new roll and the advice is solved
again from the new state. The tests check it against fixed policies and against playing it
out by sampling. $\lambda$ defaults to 10,000 EXP per point and can be set to scarce, normal or
plentiful in the app.

### Monte Carlo for farming time
Reaching a build score needs good pieces in five slots at once, and the state space is too large
for an exact chain (10 continuous bests: on-set and off-set per slot). `core/simulate.py` runs
4,000 simulated farming paths:

- Drops are drawn from a pool of 200,000 artifacts simulated exactly. Resampling the pool is
  statistically equivalent and about four times faster.
- The build score respects the 4+1 rule: on-set pieces everywhere, plus at most one off-set piece.
- Output: median, interquartile range and 90th percentile of resin and days, plus the player's
  percentile among simulated players with the same resin spent.

### Domain recommendation
`core/planner.py` computes, for every relevant domain, the expected build-score gain from one
more run for every queued character, capped at each target and weighted by priority. Characters
are compared on **common random numbers**: the same seed produces the same physical drops for
every build, so differences between domains are not noise between independent samples. Condensed
resin is recommended when the chosen domain remains the best after at least 80% of the possible
outcomes of one run.

### Stat weights derived from a damage model
Substat weights are not hand-set for damage builds. `core/talents.py` reads every character's
talent labels from the game data and works out what each hit scales on. For example,
"Charged Attack: Equitable Judgment | 14.6% Max HP". It also finds conversions such as Hu Tao's
HP-to-ATK. `core/damage.py` turns this into a relative damage function:

$$D = \sum_t e_t \left(\sum_k c_{t,k} S_k\right) (1 + \mathrm{CR}\cdot\mathrm{CD})(1 + \mathrm{DMG\%})\,A(\mathrm{EM})$$

Here $e_t$ is how much each talent counts, $c_{t,k}$ the coefficient on stat $S_k$, and $A$ the
amplifying-reaction bonus. A substat's weight is the relative damage gain from one maximum roll
of it at the character's current stats, normalised so the best substat is 1. The weights
therefore adapt to the build. Crit damage is worth little to a character already far past a
1:2 crit ratio, and flat ATK is worth more when base ATK is low.

### Build score
Per-roll weights answer "what should the next piece have", but they are the wrong tool for judging a
finished build: a character already far past a 1:2 crit ratio would see its own crit damage rolls
discounted. So the score of what a character wears is measured by damage instead. It is the damage
its artifacts add, as a share of what five flawless +20 pieces would add. Both are computed with the
character's own formula, starting from its stats without artifacts. The flawless set is built
greedily, one main stat and one roll at a time, so diminishing returns are respected. The result is 0
with no artifacts and 1 when ideal, and it is comparable across characters. Support builds keep the
average piece score.

## Known limitations and open problems

These are stated plainly because they are where the model is weakest and where the interesting
work is left:

- **Optimal stopping depends on a chosen exchange rate.** The policy is optimal for a given
  $\lambda$, but $\lambda$ itself is the player's preference. Mora and the artifact's base fodder
  EXP are left out, and the value of a better piece is linear in score.
- **Domain choice is myopic.** It looks one run ahead. Resin allocation across characters is
  naturally a Markov decision process.
- **No variance reduction in the farming simulation** beyond common random numbers. The exact
  potential is an obvious control variate.
- **No inference on real drops yet.** Sessions log resin, five-star counts and main stats, which
  is enough to test the 1.065 drop rate (Poisson/binomial) and the main stat distribution (χ²),
  or to estimate them with a Beta prior once there is data.
- **The damage model is partial.** Passives written as prose (Raiden's ER-to-DMG), set bonuses,
  team buffs and rotations are not modelled. Talent emphasis comes from talent levelling priority
  (1, ½, ¼). ER and support builds keep the substat priority from genshin-builds.com.
- **Some constants are judgement calls.** The 0.7 off-set factor, the 5% per set rank and the
  reference stats for characters without imported data are all in `core/constants.py`.

## Running it

Requires Python 3.11+ and Node 20+.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m core.importer        # loads characters, sets, domains, builds and talent data
uvicorn api.main:app --reload  # http://localhost:8000, API docs at /docs
pytest
```

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173, proxies /api to the backend
```

`DATABASE_URL` defaults to `sqlite:///genshin.db`. Any SQLAlchemy URL works, including PostgreSQL.

To refresh game data after a game update:

```bash
npm install --prefix /tmp/gdb genshin-db
node backend/scripts/export_game_data.js /tmp/gdb/node_modules/genshin-db
python backend/scripts/fetch_builds.py
python -m core.importer        # from backend/
```

## Layout

```
backend/
  core/        pure logic, no HTTP or database: scoring, markov, simulate, planner,
               damage, talents, advice, enka parsing, importer, constants
  api/         FastAPI routes; loads data, calls core, returns JSON
  db/          SQLAlchemy models and Alembic migrations
  data/        raw game data (genshin-db, datamine tables, genshin-builds.com)
  scripts/     data export and build scraping
  tests/       91 tests, including Monte Carlo checks of the exact results
frontend/
  src/pages/   Farm, Characters, Artifacts
  src/components/
  src/api/     typed client for the backend
```

Data sources: [genshin-db](https://github.com/theBowja/genshin-db),
[AnimeGameData](https://gitlab.com/Dimbreath/AnimeGameData) (datamined tables),
[Genshin Optimizer](https://github.com/frzyc/genshin-optimizer),
[genshin-builds.com](https://genshin-builds.com), [Enka.Network](https://enka.network).
