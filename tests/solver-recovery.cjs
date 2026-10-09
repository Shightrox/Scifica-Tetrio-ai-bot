const {spawn}=require('node:child_process'),assert=require('node:assert/strict'),path=require('node:path'),E=require('../engine.js');
async function run(crash){
 const p=spawn(process.execPath,[path.join(__dirname,crash?'worker-restart-runner.cjs':'../overlay-solver.cjs')]);
 const replies=[];let buffer='';
 p.stdout.on('data',b=>{buffer+=b;let i;while((i=buffer.indexOf('\n'))>=0){replies.push(JSON.parse(buffer.slice(0,i)));buffer=buffer.slice(i+1);}});
 p.stderr.on('data',b=>process.stderr.write(b));
 const send=(id,state)=>p.stdin.write(JSON.stringify({id,state})+'\n');
 async function wait(id,stage,after=-1){const deadline=performance.now()+5000;while(performance.now()<deadline){const r=replies.find((r,i)=>i>after&&r.id===id&&r.stage===stage);if(r)return r;await new Promise(r=>setTimeout(r,10));}throw Error('timeout '+id+' '+stage);}
 try{
  const base={board:E.empty(),piece:'T',start:E.entry('T',true),queue:['I','O','S','Z','J'],allowHold:false,simpleOnly:true,profile:'versus',tucks:false,attackPriority:false};
  if(crash){
   send(1,base);const restart=await wait(1,'worker-restart');
   const answer=await wait(1,'final',replies.indexOf(restart));assert(answer.result.candidates.length);
   console.log('PASS terminated background worker restarts and completes the current request');return;
  }
  send(1,{...base,queue:['I']});let r=await wait(1,'final');assert.equal(r.result.candidates[0].lookahead,2);
  send(2,base);r=await wait(2,'refined');assert(r.cache);r=await wait(2,'final');assert.equal(r.result.candidates[0].lookahead,3);
  const board=E.empty();for(let y=2;y<20;y++)board[y][3]=board[y][6]='J';
  const s={...base,board,piece:'O',start:{x:0,y:5,r:0},tucks:true,rotationSystem:'srs+',allow180:true};
  send(3,s);r=await wait(3,'final');assert(r.result.candidates.every(c=>c.pos.x<3));
  send(4,{...s,start:{x:7,y:5,r:0}});await wait(4,'fast');r=await wait(4,'final');
  assert(r.result.candidates.length&&r.result.candidates.every(c=>c.pos.x>=7));
  console.log('PASS longer NEXT gets fresh deep search; unreachable cached landings cannot suppress refinement');
  send(5,require('./survival-cases.json').at(-1));r=await wait(5,'fast');
  assert.equal(r.result.candidates[0].lookahead,2,'first emergency response already sees NEXT');
  assert.equal(r.result.candidates[0].lines,1);assert.equal(r.result.candidates[0].auto.mode,'survive');
  r=await wait(5,'final');assert(!r.continuation);assert.equal(r.result.candidates[0].intent,'downstack');
  console.log('PASS live solver returns two-piece survival before background refinement');
 }finally{p.stdin.end();setTimeout(()=>{if(p.exitCode===null)p.kill();},1000).unref();}
}
(async()=>{await run(false);await run(true);})().catch(e=>{console.error(e);process.exitCode=1;});
