'use strict';
const assert=require('node:assert/strict'),E=require('../engine'),L=require('../league-search.cjs');
const board=E.empty();board[18]=[...'XXX...XXXX'].map(v=>v==='.'?null:'J');board[19]=[...'XXXX.XXXXX'].map(v=>v==='.'?null:'J');
const base={board,piece:'L',start:E.entry('L',true),queue:['T','I','O','S','Z'],hold:null,allowHold:true,canHold:true,
 simpleOnly:true,tucks:true,rotationSystem:'srs+',allow180:true,profile:'versus',attackPriority:true,chain:{combo:0,b2b:0}};
function replay(s,c){
 for(const expected of [c,...c.future]){
  const p=E.choices(s.board,s.piece,s.queue,s.hold,s.start,true,s.allowHold&&s.canHold!==false,true,s)
   .find(p=>p.piece===expected.piece&&p.useHold===expected.useHold&&(p.spin||null)===(expected.spin||null)&&JSON.stringify(p.board)===JSON.stringify(expected.board));
  assert(p,'every construction and spin must be reachable with the actual HOLD/NEXT');
  let pos=p.useHold?E.entry(p.piece,true):s.start;
  for(const action of p.path){pos=E.move(s.board,p.piece,pos,action,'srs+');assert(pos);}
  assert.deepEqual(E.lock(s.board,p.piece,pos).board,p.board);
  s={...s,board:p.board,piece:p.nextQueue[0],queue:p.nextQueue.slice(1),hold:p.newHold,canHold:true,start:p.nextQueue.length?E.entry(p.nextQueue[0],true):null};
 }
}
for(const piece of ['O','I','S','Z','J','L']){
 const s={...base,piece,start:E.entry(piece,true),allowHold:false},r=L.find(s,{maxMs:2000,maxDepth:3}),c=r.candidates[0];
 assert.equal(c.lines,0);assert(c.future.some(p=>p.spin==='full'&&p.lines===2),'build the overhang before taking the TSD');
 assert(c.tSlot?.ready);assert(L.spinReachable(c.board,c.tSlot.pos,s));replay(s,c);
 assert.equal(L.tSlot(c.board,['I','O','S'],null,false,s).credit,0,'no credit for an unseen T');
}
const held={...base,hold:'T',queue:['I','O','S','Z']},heldChoices=L.find(held,{maxMs:2000,maxDepth:3}).candidates;
// Here HOLD T can clear the entire original field immediately. Do not force a
// slower TSD when the PC is better; retain the held-T construction alternative.
assert(heldChoices[0].useHold&&heldChoices[0].perfectClear);replay(held,heldChoices[0]);
const hc=heldChoices.find(c=>c.future.some(p=>p.useHold&&p.spin==='full'));
assert(hc,'held T must remain available to a later construction');replay(held,hc);
const mirrored={...base,piece:'J',board:board.map(r=>r.slice().reverse()),start:E.entry('J',true),allowHold:false};
const mc=L.find(mirrored,{maxMs:2000,maxDepth:3}).candidates[0];assert(mc.future.some(p=>p.spin==='full'));replay(mirrored,mc);
const sealed=E.clone(board);sealed[17][3]='J';sealed[15]=Array(9).fill('J').concat(null);
assert(!L.spinReachable(sealed,{x:3,y:17,r:2},base),'three corners behind an impassable roof are not a usable spin');
const short=L.find({...base,queue:[],allowHold:false},{maxMs:2000});assert.equal(short.candidates[0].lookahead,1);
const cancelled=L.find(base,{aborted:()=>true});assert(cancelled.budgetHit);assert.equal(cancelled.candidates[0].lookahead,1);
let chain={combo:0,b2b:0};for(let i=0;i<4;i++)chain=E.tactical({lines:4},chain,'versus');
assert.equal(E.tactical({lines:1},chain,'versus').surge,0,'four difficult clears display B2B x3');
chain=E.tactical({lines:4},chain,'versus');assert.equal(E.tactical({lines:1},chain,'versus').surge,4);
assert.equal(E.tactical({lines:0},chain,'versus').surge,0,'empty placement preserves charge');
assert.equal(E.tactical({lines:1,spin:'mini'},chain,'versus').surge,0,'a mini preserves B2B');
console.log('PASS six overhang builders, mirrored TSD, held-T continuation, inaccessible slot, preview/cancel bounds and League Surge indexing');
