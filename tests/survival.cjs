const assert=require('node:assert/strict'),E=require('../engine.js'),Attack=require('../attack-search.cjs');
const cases=require('./survival-cases.json');
const last=cases.at(-1),before=E.metrics(last.board);
const c=E.analyze({...last,depth:2,rootLimit:6,beamWidth:2,futureTucks:false}).candidates[0];
assert.equal(c.auto.mode,'survive');assert.equal(c.intent,'downstack');
assert.equal(c.lines,1,'clear the roof instead of placing another layer');
assert.equal(c.future[0].lines,1);assert(c.metrics.garbageAccess<before.garbageAccess);
assert.equal(E.metrics(c.future[0].board).garbageAccess,0,'open the top garbage entrance using NEXT');
for(const s of cases){
 const a=E.analyze({...s,depth:2,rootLimit:6,beamWidth:2,futureTucks:false}).candidates[0];
 assert.equal(a.lookahead,2);assert(a.nextSafe);assert.equal(a.auto.mode,'survive');
 assert(a.metrics.height<=E.metrics(s.board).height,'these escape fixtures do not need a taller tower');
 assert.equal(Attack.find(s).sequence,null,'a pressure continuation cannot take over survival');
}
const board=E.empty();for(let y=12;y<20;y++)board[y]=Array(9).fill('G').concat(null);
const s={...last,board,piece:'O',start:E.entry('O',true),hold:'I',canHold:true,allowHold:true,queue:['T','S','Z','J','L'],chain:{combo:9,b2b:12}};
assert.equal(E.metrics(board).holes,0);assert.equal(E.autoPolicy(E.metrics(board)).mode,'survive','open garbage still consumes headroom');
const on=E.analyze({...s,depth:3}),off=E.analyze({...s,depth:3,attackPriority:false});
assert(on.candidates[0].useHold&&on.candidates[0].garbageCleared===4);
assert.deepEqual(on.candidates.map(c=>c.value),off.candidates.map(c=>c.value),'pressure rewards stay off across the entire emergency horizon');
assert.equal(E.autoPolicy(E.metrics(E.empty())).mode,'attack');
console.log('PASS garbage headroom, two-piece roof escape, pressure isolation and safe return to attack');
