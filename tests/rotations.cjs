const assert=require('node:assert/strict'),E=require('../engine.js');
const rules={rotationSystem:'srs+',allow180:true};
const key=(t,p)=>E.SHAPES[t][p.r].map(([x,y])=>[x+p.x,y+p.y].join(',')).sort().join(';');
for(const sample of require('./rotation-cases.json')){
 const board=E.empty();sample.rows.forEach((r,i)=>board[20-sample.rows.length+i]=[...r].map(v=>v==='X'?'G':null));
 const start=E.entry(sample.piece,true),target=key(sample.piece,sample.target);
 const candidates=E.placements(board,sample.piece,start,true,false,true,rules);
 const c=candidates.find(c=>key(sample.piece,c.pos)===target);
 assert(c&&c.requiresSoftDrop&&c.lines===1,sample.name);
 assert.deepEqual(c.path,sample.path);
 const old=sample.piece==='I'?{rotationSystem:'srs',allow180:false}:{...rules,allow180:false};
 assert(!E.placements(board,sample.piece,start,true,false,true,old).some(p=>key(sample.piece,p.pos)===target),'new route unavailable with the old rotation rules');
 for(const p of candidates){
  let pos=start;
  for(const [i,a] of p.path.entries()){
   pos=E.move(board,p.piece,pos,a,rules.rotationSystem);assert(pos);
   assert.deepEqual(pos,p.route[i].pos);
  }
  assert.deepEqual(pos,p.pos);assert.deepEqual(E.lock(board,p.piece,pos).board,p.board);
 }
 const uncertain=E.placements(board,sample.piece,{...start,uncertain:true},true,false,true,rules);
 assert(uncertain.every(p=>p.path.every(a=>['L','R','SD'].includes(a))),'unknown orientation never guesses a rotation');
}
// First successful kick matters: three legal horizontal I trials are not
// interchangeable. SRS+ mirrors the preference on the opposite side.
let b=E.empty();b[8][5]='G';
assert.deepEqual(E.rotation(b,'I',{x:3,y:7,r:0},'CW','srs+'),{pos:{x:4,y:7,r:1},kick:1});
assert.deepEqual(E.rotation(b,'I',{x:3,y:7,r:0},'CW','srs'),{pos:{x:1,y:7,r:1},kick:1});
b=E.empty();b[8][4]='G';
assert.deepEqual(E.rotation(b,'I',{x:3,y:7,r:0},'CCW','srs+'),{pos:{x:2,y:7,r:3},kick:1});
// A real half turn reaches a slot that two quarter turns cannot reproduce.
b=E.empty();b[17][7]='G';b[17][9]='G';for(let x=0;x<7;x++)b[19][x]='G';
const before={x:7,y:17,r:2};
assert(E.fits(b,'J',before));
for(const action of ['CW','CCW']){const first=E.move(b,'J',before,action,'srs+'),second=first&&E.move(b,'J',first,action,'srs+');assert(!second||key('J',second)!==key('J',{x:7,y:18,r:0}));}
assert.deepEqual(E.move(b,'J',before,'180','srs+'),{x:7,y:18,r:0});
// I half turns have only the axis kick, never JLSTZ's diagonals.
b=E.empty();b[19][6]='G';
assert.deepEqual(E.rotation(b,'I',{x:3,y:17,r:0},'180','srs+'),{pos:{x:3,y:16,r:2},kick:1});
b=E.empty();b[15][4]='G';
assert.deepEqual(E.rotation(b,'I',{x:3,y:15,r:1},'180','srs+'),{pos:{x:4,y:15,r:3},kick:1});
// Index four in the six-trial 180 table is not the 90-degree fin kick.
b=E.empty();b[17][3]='J';b[18]=[...'XXX...XXXX'].map(v=>v==='.'?null:'J');b[19]=[...'XXXX.XXXXX'].map(v=>v==='.'?null:'J');
assert.equal(E.spinType(b,'T',{x:3,y:17,r:1},4,true),'mini');
console.log('PASS SRS+ I kick preference, true 180 roof tuck, I axis-only half kick, spin classification and all fixture routes');
