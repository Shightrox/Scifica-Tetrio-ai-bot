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
 // A proved PC must survive new preview tails and a real HOLD transition.
 s=structuredClone(require('./pc-cases.json')[0]);
 const initial=structuredClone(s);let id=100,locks=0,holds=0;
 while(locks<4){
  send(id,s);r=await response(id++,'final');let c=r.result.candidates[0];
  assert(c.pcVerified);assert.equal(c.pcPieces,4-locks);
  if(locks)assert(r.continuation,'keep the proved sequence when unseen NEXT tails appear');
  if(c.useHold){
   const old=s.piece;
   s={...s,piece:c.piece,hold:old,queue:s.hold?s.queue:s.queue.slice(1),canHold:false,start:E.entry(c.piece,true)};
   while(s.queue.length<5)s.queue.push('I');
   send(id,s);r=await response(id++,'final');c=r.result.candidates[0];
   assert(r.continuation&&c.pcVerified&&!c.useHold,'HOLD acknowledgement continues the same proof');holds++;
  }
  s={...s,board:c.board,piece:s.queue[0],queue:s.queue.slice(1),hold:c.newHold,canHold:true,
     start:E.entry(s.queue[0],true),chain:{combo:c.chain.combo,b2b:c.chain.b2b}};
  while(s.queue.length<5)s.queue.push('I');locks++;
 }
 assert(holds>0);assert(s.board.every(row=>row.every(v=>!v)));
 send(120,{...initial,queue:[...initial.queue.slice(0,4),'Z']});r=await response(120);
 assert(!r.cache&&!r.continuation,'fifth preview cell participates in cache identity');
 send(121,{...initial,attackPriority:false});r=await response(121);
 assert(!r.cache&&!r.continuation,'strategy switch invalidates a pressure proof');
 const changed=structuredClone(initial);changed.board[15][5]='G';
 send(122,changed);r=await response(122);assert(!r.continuation&&!r.cache,'new garbage invalidates a PC proof');
 console.log('PASS four-lock PC through new NEXT tails and HOLD; strategy, fifth preview and board changes invalidate reuse');
 // Surface routes retain checkpoints/spin evidence when rebased at a new pose.
 board=E.empty();board[17][3]='J';board[18]=[...'XXX...XXXX'].map(v=>v==='.'?null:'J');board[19]=[...'XXXX.XXXXX'].map(v=>v==='.'?null:'J');
 s={...initial,board,piece:'T',start:E.entry('T',true),hold:null,allowHold:false,tucks:true,rotationSystem:'srs+',allow180:true,queue:['I','S','O','J']};
 send(130,s);r=await response(130,'final');assert.equal(r.result.candidates[0].spin,'full');
 send(131,{...s,start:{x:3,y:3,r:1},queue:[...s.queue,'Z']});r=await response(131,'final');
 assert(r.cache,'a newly revealed tail can reuse verified known-prefix analysis');
 let native=r.result.candidates[0],pos={x:3,y:3,r:1};assert.equal(native.spin,'full');
 for(const [i,a] of native.path.entries()){pos=E.move(board,native.piece,pos,a,'srs+');assert.deepEqual(pos,native.route[i].pos);}
 assert(native.requiresSoftDrop);assert.deepEqual(pos,native.pos);
 send(132,{...s,tucks:false});r=await response(132);assert(!r.cache);assert(!r.result.candidates[0].spin);
 send(133,{...s,allow180:false});r=await response(133);assert(!r.cache&&!r.continuation);assert(r.result.candidates.every(c=>!c.path.includes('180')));
 send(134,{...s,rotationSystem:'srs'});r=await response(134);assert(!r.cache&&!r.continuation);
 send(135,{...s,start:{...s.start,uncertain:true}});r=await response(135);assert(!r.cache);assert(r.result.candidates.every(c=>c.path.every(a=>['L','R','SD'].includes(a))));
 console.log('PASS native T-spin checkpoint rebase, newly revealed queue tail, movement-mode cache exclusion');
 for(let id=140;id<150;id++){send(id,{...s,queue:['S','I','O','J','Z'],start:{x:3,y:Math.floor((id-140)/3)-2,r:0}});await wait(12);}
 r=await response(149,'final');assert(r.result.candidates.length);
 const nativeFirsts=[];for(let id=140;id<150;id++){const first=replies.find(r=>r.id===id&&r.result);if(first)nativeFirsts.push(first.elapsed);}
 nativeFirsts.sort((a,b)=>a-b);
 console.log('Native first-answer IPC ms p50/p95:',nativeFirsts[Math.floor(nativeFirsts.length*.5)].toFixed(1),nativeFirsts.at(-1).toFixed(1));
}finally{p.stdin.end();}})().catch(e=>{console.error(e);process.exitCode=1;p.kill();});
