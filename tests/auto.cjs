const assert=require('node:assert/strict'),E=require('../engine.js');
const cases=require('./strategy-v12-cases.json');
function replay(s,c){
 let board=s.board,queue=s.queue.slice(),hold=s.hold,piece=s.piece;
 for(const [i,p] of [c,...c.future].entries()){
  let start=i===0?s.start:E.entry(piece,true);
  if(p.useHold){const replacement=hold||queue.shift();assert.equal(p.piece,replacement);hold=piece;piece=replacement;start=E.entry(piece,true);}
  assert.equal(p.piece,piece);
  const valid=E.placements(board,piece,start,true).some(x=>JSON.stringify(x.board)===JSON.stringify(p.board)&&x.lines===p.lines);
  assert(valid,'planned continuation must really be reachable with available HOLD/NEXT');
  board=p.board;piece=queue.shift();
 }
}
let b=E.empty();for(let y=16;y<20;y++)b[y]=Array(9).fill('L').concat(null);
assert.equal(E.autoPolicy(E.metrics(b)).mode,'attack');
assert(E.setupPotential(E.metrics(b),['I'],null,false)>0);
assert.equal(E.setupPotential(E.metrics(b),[],null,true),0,'no bank reward for an unknown future I');
assert.equal(E.setupPotential(E.metrics(b),[],'I',false),0,'disabled HOLD cannot supply an I');
assert(E.setupPotential(E.metrics(b),[],'I',true)>0);
const q={board:b,piece:'O',hold:'I',queue:['T','S','Z','L','J'],start:E.entry('O',true),allowHold:true,simpleOnly:true,profile:'versus',depth:3,rootLimit:8,beamWidth:3};
let c=E.analyze(q).candidates[0];assert(c.useHold&&c.lines===4&&c.perfectClear);replay(q,c);
console.log('PASS known I/HOLD-dependent setup, immediate held-I quad, executable future sequence');

// Fully prepared four rows, plus a low partial upper layer: hold the quad
// opportunity only until the I arrives; never reward towers above four rows.
const four=E.metrics(b);for(let y=12;y<16;y++)b[y]=Array(9).fill('L').concat(null);
assert(E.setupPotential(E.metrics(b),[],'I',true)<=E.setupPotential(four,[],'I',true));
for(let y=7;y<12;y++)b[y]=Array(9).fill('G').concat(null);
assert.equal(E.autoPolicy(E.metrics(b)).mode,'survive');assert.equal(E.setupPotential(E.metrics(b),[],'I',true),0);
c=E.analyze({...q,board:b}).candidates[0];assert.equal(c.auto.mode,'survive');assert.equal(c.intent,'downstack');assert(c.lines===4&&c.metrics.height<13);
const middle=E.empty();for(let y=10;y<20;y++)middle[y][0]='J';assert.equal(E.autoPolicy(E.metrics(middle)).mode,'balance');
assert.equal(E.autoPolicy(E.metrics(E.empty())).mode,'attack','return to attack after the board is cleared');
console.log('PASS automatic attack/balance/survival and return, no reward for excessive or dangerous towers');

const s={...cases[11],depth:3,rootLimit:8,beamWidth:3};
c=E.analyze(s).candidates[0];
assert.equal(c.intent,'combo');assert.equal(c.lines,1);assert.deepEqual(c.future.map(p=>p.lines),[1,1]);
assert.equal(E.metrics(c.future[0].board).garbageCover,0);assert.equal(E.metrics(c.future.at(-1).board).holes,0);replay(s,c);
console.log('PASS low stack uses HOLD for three successive clears instead of one double; next piece removes temporary cover');

const trap=require('./next-piece-trap-v12.json');c=E.analyze(trap).candidates[0];assert(c.nextSafe);
assert(E.placements(c.board,trap.queue[0],E.entry(trap.queue[0],true),true,true).length);
console.log('PASS fast survival still protects the next piece from top-out');
