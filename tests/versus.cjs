const assert=require('node:assert/strict'),E=require('../engine.js');
for(const t of Object.keys(E.BASE))for(const c of E.placements(E.empty(),t,{...E.spawn(t),y:-2},true)){
 let pos={...E.spawn(t),y:-2},drop=false;
 for(const a of c.path){if(a==='D')drop=true;else assert(!drop,'no actions after descent');pos=E.move(E.empty(),t,pos,a);assert(pos);}
 assert.deepEqual(pos,c.pos);
}
let q=E.tactical({lines:4,perfectClear:false},{combo:1,b2b:2},'versus');assert.equal(q.combo,2);assert.equal(q.b2b,3);assert(q.reward>36);
let n=E.tactical({lines:0},{combo:3,b2b:4},'versus');assert.equal(n.combo,0);assert.equal(n.b2b,4);
let single=E.tactical({lines:1},{combo:0,b2b:4},'versus');assert.equal(single.b2b,0);
assert(E.tactical({lines:1,perfectClear:true},{},'versus').reward>single.reward);
console.log('PASS: executable-only routes, combo continuation/reset, quad B2B, perfect-clear preference');
