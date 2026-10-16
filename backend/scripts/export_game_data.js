// Export the game data the planner needs from the genshin-db npm package into data/.
//   npm install --prefix /tmp/gdb genshin-db
//   node scripts/export_game_data.js /tmp/gdb/node_modules/genshin-db

const fs = require('fs')
const path = require('path')

const db = require(path.resolve(process.argv[2]))
const out = path.join(__dirname, '..', 'data')
const opts = { matchCategories: true, verboseCategories: true }
const TALENT_LEVEL = 10
const TALENTS = { combat1: 'normal', combat2: 'skill', combat3: 'burst' }

const write = (name, data) => fs.writeFileSync(path.join(out, name), JSON.stringify(data, null, 2) + '\n')

write('characters.json', db.characters('names', opts).map((c) => {
  const base = c.stats(90)
  return {
    id: c.id, name: c.name, element: c.elementText, weapon: c.weaponText, rarity: c.rarity,
    base: { hp: base.hp, atk: base.attack, def: base.defense },
    ascension: { stat: c.substatText, value: base.specialized },
  }
}))

write('artifacts.json', db.artifacts('names', opts).map((a) => ({
  id: a.id, name: a.name, rarity: a.rarityList, effect2Pc: a.effect2Pc, effect4Pc: a.effect4Pc,
})))

write('domains.json', db.domains('names', opts).filter((d) => d.domainText === 'Artifacts').map((d) => ({
  id: d.id, name: d.name, entrance: d.entranceName, region: d.regionName,
  rewards: d.rewardPreview.filter((r) => r.rarity).map((r) => ({ id: r.id, name: r.name, rarity: r.rarity })),
})))

// each talent's labels with its parameter values at TALENT_LEVEL
const talents = {}
for (const name of db.talents('names', { matchCategories: true })) {
  const t = db.talents(name)
  talents[name] = Object.fromEntries(Object.entries(TALENTS).filter(([k]) => t[k]).map(([k, kind]) => {
    const { labels, parameters } = t[k].attributes
    const values = Object.fromEntries(Object.entries(parameters).map(([p, v]) => [p, v[TALENT_LEVEL - 1]]))
    return [kind, { name: t[k].name, labels, values }]
  }))
}
write('talents.json', talents)

console.log('genshin-db', require(path.join(path.resolve(process.argv[2]), 'package.json')).version)
