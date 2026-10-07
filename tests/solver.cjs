const {spawn}=require('node:child_process');const assert=require('node:assert/strict');const E=require('../engine.js');
const p=spawn(process.execPath,[require('node:path').join(__dirname,'../overlay-solver.cjs')]);const replies=[];let pending='';const timings=new Map();
p.stdout.on('data',b=>{pending+=b;let i;while((i=pending.indexOf('\n'))>=0){const r=JSON.parse(pending.slice(0,i));pending=pending.slice(i+1);r.elapsed=performance.now()-timings.get(r.id);replies.push(r);}});
p.stderr.on('data',b=>process.stderr.write(b));
const wait=ms=>new Promise(r=>setTimeout(r,ms));const send=(id,state)=>{timings.set(id,performance.now());p.stdin.write(JSON.stringify({id,state})+'\n');};
async function response(id,stage){const until=performance.now()+4000;while(performance.now()<until){const r=replies.find(r=>r.id===id&&(!stage||r.stage===stage));if(r)return r;await wait(5);}throw Error('Timeout '+id+' '+stage);}
(async()=>{try{
 let board=E.empty();for(let y=16;y<20;y++)board[y]=Array(9).fill('G').concat(null);
 let s={board,piece:'O',start:{x:4,y:-2,r:0},hold:'I',queue:['T','S','Z','L','J'],allowHold:true,canHold:true,simpleOnly:true,profile:'versus',chain:{combo:0,b2b:0}};
 send(1,s);let r=await response(1,'final');assert(r.result.candidates[0].useHold);assert.equal(r.result.candidates[0].lines,4);
 send(2,{...s,canHold:false});r=await response(2);assert(r.result.candidates.every(c=>!c.useHold));assert(!r.cache);
 send(3,{...s,hold:'J'});r=await response(3);assert(!r.cache);assert(r.result.candidates.every(c=>!c.useHold||c.piece==='J'));
 s={...s,board:E.empty(),piece:'T',hold:'I',queue:['S','Z','I','O','J'],start:{x:3,y:-2,r:0}};
 // Continuous moving-piece updates must not starve deep answers.
 for(let id=10;id<40;id++){send(id,{...s,start:{x:3+id%2,y:Math.floor((id-10)/10)-2,r:0}});await wait(7);}
 r=await response(39,'final');assert(r.result.candidates[0].lookahead===3);
 const firsts=[];for(let id=10;id<40;id++){const a=replies.find(r=>r.id===id&&r.result);if(a)firsts.push(a.elapsed);}firsts.sort((a,b)=>a-b);
 console.log('PASS HOLD-aware cache, canHold exclusion, latest-position deep answer amid 30 moving frames');
 console.log('First-answer IPC ms p50/p95:',firsts[Math.floor(firsts.length*.5)].toFixed(1),firsts[Math.floor(firsts.length*.95)].toFixed(1));
}finally{p.stdin.end();}})().catch(e=>{console.error(e);process.exitCode=1;p.kill();});
