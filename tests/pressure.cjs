'use strict';
const assert=require('node:assert/strict');
const E=require('../engine.js'),PC=require('../perfect-clear.cjs');
const cases=require('./pc-cases.json');

function replay(state,sequence){
  let board=state.board,piece=state.piece,queue=state.queue.slice(),hold=state.hold,start=state.start;
  let attack=0,chain=state.chain||{},held=false;
  for(const {candidate:c} of sequence){
    if(c.useHold){
      assert(state.allowHold);const old=piece;piece=hold||queue.shift();hold=old;
      start=E.entry(piece,true);held=true;
    }
    assert.equal(c.piece,piece,'uses only an observed piece or HOLD');
    let pos=start,descending=false;
    for(const a of c.path){
      if(a==='D')descending=true;else assert(!descending,'native route cannot move after soft drop');
      pos=E.move(board,piece,pos,a);assert(pos,'every move is reachable');
    }
    assert.deepEqual(pos,c.pos);
    const locked=E.lock(board,piece,pos);assert.deepEqual(locked.board,c.board);
    assert.equal(locked.lines,c.lines);
    const event=E.tactical(c,chain,'versus');attack+=event.attackEstimate;
    chain=event;board=locked.board;piece=queue.shift();start=piece?E.entry(piece,true):null;
  }
  assert(board.every(row=>row.every(v=>!v)),'entire field clears');
  assert.equal(attack,sequence[0].candidate.attackPlan);
  return held;
}

for(const s of cases){
  const result=PC.find(s,{maxMs:500});
  assert.equal(result.status,'solved');assert.equal(result.sequence.length,4);
  assert(replay(s,result.sequence),'fixture exercises HOLD');
  assert(result.sequence[0].candidate.pcVerified);
  const beam=E.analyze({...s,depth:3,rootLimit:8,beamWidth:3});
  assert(!beam.candidates[0].future.some(p=>p.perfectClear),'three-piece horizon misses four-piece completion');
}
console.log('PASS 3 distinct four-piece PCs: replayed SRS paths, HOLD/NEXT order, exact empty board and attack totals');

// The optimized bitboard candidates must agree with the full movement engine.
for(const s of cases)for(const piece of Object.keys(E.BASE)){
  const rows=PC.bitmap(s.board);
  const reachable=E.placements(s.board,piece,E.entry(piece,true),true);
  for(const drop of PC.drops(rows,piece,6)){
    const candidate=reachable.find(p=>p.pos.x===drop.pos.x&&p.pos.y===drop.pos.y&&p.pos.r===drop.pos.r);
    // Symmetric I/S/Z poses may use a different origin/rotation in the BFS.
    assert(candidate||reachable.some(p=>JSON.stringify(PC.bitmap(p.board))===JSON.stringify(drop.rows)));
    const locked=E.lock(s.board,piece,drop.pos);
    assert.deepEqual(PC.bitmap(locked.board),drop.rows);assert.equal(locked.lines,drop.lines);
  }
}
console.log('PASS bitboard placements agree with ordinary engine for all seven pieces');

let s=cases[0];
assert.equal(PC.find({...s,queue:s.queue.slice(0,2)},{maxMs:500}).sequence,null,'does not invent unseen pieces');
assert.equal(PC.find(s,{maxNodes:0,maxMs:500}).status,'budget','bounded work has a distinct status');
let odd=E.clone(s.board);odd[0][0]='G';assert.equal(PC.find({...s,board:odd}).status,'ineligible');
let high=E.empty();for(let y=6;y<20;y++)high[y]=Array(9).fill('G').concat(null);
const danger={...s,board:high,piece:'I',start:E.entry('I',true),hold:null,allowHold:false,queue:['O','T']};
assert.equal(PC.find(danger).status,'ineligible');
const cautious=E.analyze({...danger,depth:1,attackPriority:false}).candidates[0];
const aggressive=E.analyze({...danger,depth:1,attackPriority:true}).candidates[0];
assert.equal(aggressive.intent,'downstack');assert.deepEqual(aggressive.pos,cautious.pos);
assert.equal(aggressive.value,cautious.value,'survival overrides attack priority');
let four=E.empty();for(let y=16;y<20;y++)four[y]=Array(9).fill('J').concat(null);
const held={...s,board:four,piece:'O',start:E.entry('O',true),hold:'I',allowHold:true,canHold:true,queue:[]};
const result=PC.find(held,{maxMs:500});assert.equal(result.sequence[0].candidate.useHold,true);replay(held,result.sequence);
assert.equal(PC.find({...held,canHold:false},{maxMs:500}).sequence,null);
assert.equal(PC.find({...held,allowHold:false},{maxMs:500}).sequence,null);
assert(E.tactical({lines:1},{combo:3,b2b:0},'versus').attackEstimate>0,'long single chains send garbage');
assert.equal(E.tactical({lines:0},{combo:3,b2b:4},'versus').attackEstimate,0);
console.log('PASS unknown-queue, HOLD lockout, parity, budget, combo-floor and survival guards');
