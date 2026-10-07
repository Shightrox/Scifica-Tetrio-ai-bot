const assert=require('node:assert/strict');
const E=require('../engine.js');
for(const t of Object.keys(E.BASE)){
 const board=E.empty(),ps=E.placements(board,t);assert(ps.length>=9,t+' placements');
 for(const c of ps){let pos=E.spawn(t);for(const a of c.path){pos=E.move(board,t,pos,a);assert(pos,t+' path valid');}assert.deepEqual(pos,c.pos);assert.equal(E.move(board,t,pos,'D'),null);assert.equal(c.board.flat().filter(Boolean).length,4);}
}
let b=E.empty();for(let y=16;y<20;y++)for(let x=0;x<9;x++)b[y][x]='X';
let result=E.analyze({board:b,piece:'I',queue:[],depth:1,allowHold:false});assert.equal(result.candidates[0].lines,4);assert.equal(result.candidates[0].board.flat().filter(Boolean).length,0);
b=E.empty();b[15][2]='X';assert.equal(E.metrics(b).holes,4);
let p={x:-1,y:4,r:1};assert(E.fits(E.empty(),'T',p));let kicked=E.move(E.empty(),'T',p,'CCW');assert(kicked);assert.equal(kicked.x,0);
let board=E.empty(),queue=['S','T','Z','I','O','J','L'],hold=null;
for(let turn=0;turn<70;turn++){
 const piece=queue.shift();queue.push(...(queue.length<5?['L','J','O','I','Z','T','S']:[]));
 const r=E.analyze({board,piece,queue,hold,depth:2});assert(r.candidates.length,'survives turn '+turn);const c=r.candidates[0];let pos=E.spawn(c.piece);
 for(const a of c.path){pos=E.move(board,c.piece,pos,a);assert(pos,'reachable turn '+turn);}
 const locked=E.lock(board,c.piece,pos);assert.deepEqual(locked.board,c.board);board=c.board;hold=c.newHold;queue=c.nextQueue;
}
console.log('PASS: all 7 shapes, path replay, four-line clear, holes, wall kick, 70 planned turns');
