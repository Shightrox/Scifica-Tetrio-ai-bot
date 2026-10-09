const assert=require('node:assert/strict'),E=require('../engine.js');
const rules={rotationSystem:'srs+',allow180:true};
const key=(t,p)=>E.SHAPES[t][p.r].map(([x,y])=>[p.x+x,p.y+y].join(',')).sort().join(';');
// Previously: SD, CCW, CCW, CCW, SD. All those surface turns were unnecessary.
const board=E.empty();
['....XX...X','.XX..X.XXX','.XXXXX.X.X','.XX.XXXXXX','.XX.XXXXX.','.XX.XXXXXX','.XXXXXXXXX','.XX.XXXXXX']
 .forEach((r,i)=>board[12+i]=[...r].map(v=>v==='X'?'J':null));
const target=key('I',{x:-2,y:16,r:1});
const c=E.placements(board,'I',E.entry('I',true),true,false,true,rules).find(c=>key('I',c.pos)===target&&!c.spin);
assert(c);assert(!c.requiresSoftDrop);assert.deepEqual(c.path,['CCW','L','L','L','L','SD']);
// Every directly reachable landing retains a route without an interior SD.
for(const b of [E.empty(),board])for(const piece of Object.keys(E.BASE)){
 const start=E.entry(piece,true),native=E.placements(b,piece,start,true,false,true,rules);
 for(const direct of E.placements(b,piece,start,true,false,false,rules)){
  const match=native.find(c=>!c.spin&&key(piece,c.pos)===key(piece,direct.pos));
  assert(match&&!match.requiresSoftDrop,piece+' direct landing must stay direct');
 }
}
const half=E.placements(E.empty(),'T',E.entry('T',true),true,false,true,rules).find(c=>c.pos.x===3&&c.pos.r===2);
assert.deepEqual(half.path,['180','SD']);assert(!half.requiresSoftDrop);
// Identical HOLD resets position and escapes a pocket; at spawn it adds nothing.
const pockets=E.empty();for(let y=2;y<20;y++)pockets[y][3]=pockets[y][6]='J';
const held=E.choices(pockets,'O',['I','T'],'O',{x:7,y:5,r:0},true,true,true,rules);
assert(held.some(c=>c.useHold&&c.pos.x<7));
assert(!E.choices(E.empty(),'O',[],'O',E.entry('O',true),true,true,true,rules).some(c=>c.useHold));
for(const garbageCleared of [1,4]){
 assert.equal(E.tactical({lines:4,garbageCleared},{},'versus').attackEstimate,5);
 assert.equal(E.tactical({lines:4,garbageCleared},{combo:4,b2b:1},'versus').attackEstimate,11);
 assert.equal(E.tactical({lines:2,spin:'full',garbageCleared},{},'versus').attackEstimate,5);
 assert.equal(E.tactical({lines:1,spin:'mini',garbageCleared},{},'versus').attackEstimate,1);
 assert.equal(E.tactical({lines:2,garbageCleared},{},'versus').attackEstimate,1);
 assert.equal(E.tactical({lines:0,garbageCleared},{},'versus').attackEstimate,0);
 assert.equal(E.tactical({lines:4,perfectClear:true,garbageCleared},{},'versus').attackEstimate,10);
}
const state={board:E.empty(),piece:'T',start:E.entry('T',true),queue:['I','O','S','Z','J'],hold:'L',allowHold:true,simpleOnly:true,tucks:true,...rules};
const quick=E.analyze({...state,depth:1}),bounded=E.analyze({...state,depth:6,maxMs:0});
assert(bounded.budgetHit);assert.deepEqual(bounded.candidates,quick.candidates,'incomplete layers cannot bias root selection');
const {replay}=require('../scripts/replay_trace.cjs');
const candidate=quick.candidates[0],event={schema:2,version:'test',advice:{state,candidate}};
assert.equal(replay(JSON.stringify(event)).failures.length,0);
const corrupt=structuredClone(event);corrupt.advice.candidate.path=['L'];
assert.equal(replay(JSON.stringify(corrupt)).failures.length,1,'offline replay catches a bad path without a game');
console.log('PASS direct-drop dominance, early 180, identical HOLD escape, flat garbage bonus and fair search deadlines');
