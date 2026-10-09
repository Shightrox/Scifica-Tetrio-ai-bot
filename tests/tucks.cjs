const assert=require('node:assert/strict'),E=require('../engine.js'),Attack=require('../attack-search.cjs');
const board=E.empty();board[17][3]='J';
board[18]=[...'XXX...XXXX'].map(x=>x==='.'?null:'J');board[19]=[...'XXXX.XXXXX'].map(x=>x==='.'?null:'J');
const state={board,piece:'T',start:E.entry('T',true),queue:['I','S','O','J','Z'],hold:null,allowHold:true,canHold:true,
 simpleOnly:true,tucks:true,profile:'versus',attackPriority:true,chain:{combo:0,b2b:0}};
let result=E.analyze({...state,depth:1}),c=result.candidates[0];
assert.equal(c.spin,'full');assert.equal(c.lines,2);assert(c.requiresSoftDrop);assert.deepEqual(c.path,['CW','SD','CW']);
assert(!E.placements(board,'T',state.start,true).some(p=>p.lines===2),'straight-drop mode cannot enter the slot');
assert.equal(c.chain.attackEstimate,4);assert.equal(c.chain.b2b,1);
assert.equal(E.spinType(board,'T',c.pos,null),null,'shape alone is not evidence of rotation');
assert.equal(E.spinType(board,'T',{...c.pos,r:1},0),'mini');
assert.equal(E.spinType(board,'T',{...c.pos,r:1},4),'full','fifth kick upgrades a three-corner mini');
const held=E.analyze({...state,piece:'O',start:E.entry('O',true),hold:'T',depth:1}).candidates[0];
assert(held.useHold&&held.spin==='full'&&held.lines===2,'HOLD can supply the missing T');
for(const b of [E.empty(),board])for(const t of Object.keys(E.BASE))for(const p of E.placements(b,t,E.entry(t,true),true,false,true)){
 let pos=E.entry(t,true),kick=null;
 for(const [i,a] of p.path.entries()){
  const rotated=a==='CW'||a==='CCW'?E.rotation(b,t,pos,a):null;
  pos=E.move(b,t,pos,a);assert(pos);kick=rotated?.kick??null;
  if(p.route)assert.deepEqual(pos,p.route[i].pos);
 }
 assert.deepEqual(pos,p.pos);assert.deepEqual(E.lock(b,t,pos).board,p.board);
 if(p.spin)assert.equal(E.spinType(b,t,pos,kick),p.spin);
}
const well=E.empty();for(let y=8;y<20;y++)well[y]=['J','J','J','J',null,null,'J','J','J','J'];
const chain=Attack.find({...state,board:well,piece:'O',start:E.entry('O',true),queue:['O','O','O','O','O'],allowHold:false}, {maxMs:1000,maxNodes:1000});
assert.equal(chain.sequence.length,6);assert.equal(chain.sequence[0].candidate.comboPlan,6);
assert(chain.sequence.every(p=>p.candidate.lines===2));assert(chain.sequence.at(-1).candidate.perfectClear);
assert.equal(Attack.find({...state,board:well,piece:'O',start:E.entry('O',true),queue:['O'],allowHold:false},{maxMs:1000}).sequence.length,2,'no unseen pieces');
assert.equal(Attack.find(state,{maxMs:0}).sequence,null,'budget respected');
console.log('PASS grounded T-spin double, HOLD entry, mini/fifth-kick classification, all surface routes replayed');
console.log('PASS six-clear known-queue chain, truncated queue and search budget');
