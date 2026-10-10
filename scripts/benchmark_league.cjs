// Identical observed queues and deterministic garbage; no live opponent/input.
'use strict';
const fs=require('node:fs'),path=require('node:path'),{execFileSync}=require('node:child_process');
const E=require('../engine'),League=require('../league-search.cjs'),PC=require('../perfect-clear.cjs'),Attack=require('../attack-search.cjs');
const baseline='0ead5a426a48c01c9fe826563f89127af1c776ea',root=path.join(__dirname,'..');
function historical(file,imports){const m={exports:{}};new Function('module','require',execFileSync('git',['show',baseline+':'+file],{cwd:root,encoding:'utf8'}))(m,imports);return m.exports;}
const old=historical('engine.js',require),oldPC=historical('perfect-clear.cjs',id=>id==='./engine.js'?old:require(id));
const oldAttack=historical('attack-search.cjs',id=>id==='./engine.js'?old:require(id));globalThis.Tetris=E;
const output=path.resolve(process.argv[2]||'work/league-results.json'),turns=Number(process.env.SCIFICA_BENCH_TURNS||80);
const seeds=(process.env.SCIFICA_BENCH_SEEDS||'7,19,31,83').split(',').map(Number);fs.mkdirSync(path.dirname(output),{recursive:true});
function choose(s,updated){
 const e=updated?E:old,pcEngine=updated?PC:oldPC,attackEngine=updated?Attack:oldAttack;
 const pressure=e.autoPolicy(e.metrics(s.board)).mode!=='survive',pc=pressure?pcEngine.find(s):null;
 let c;
 if(updated&&pressure)c=League.find(s).candidates[0];
 if(pc?.sequence){const quick=c||e.analyze({...s,depth:1}).candidates[0];if(pc.sequence[0].candidate.value>=quick?.value)c=pc.sequence[0].candidate;}
 if(!c)c=e.analyze({...s,depth:pressure?6:3,rootLimit:pressure?6:8,beamWidth:3,maxMs:pressure?140:90}).candidates[0];
 if(pressure){const a=attackEngine.find(s).sequence?.[0].candidate;if(a&&a.value>c?.value)c=a;}
 return c;
}
function run(seed,updated,garbage){
 const rng=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296),queue=[];
 while(queue.length<turns+20){const bag=[...'IOTSZJL'];for(let i=6;i;i--){const j=Math.floor(rng()*(i+1));[bag[i],bag[j]]=[bag[j],bag[i]];}queue.push(...bag);}
 const holes=Array.from({length:60},()=>Math.floor(rng()*10));let board=E.empty(),hold=null,chain={combo:0,b2b:0};
 if(garbage)for(let y=14;y<20;y++)board[y]=Array.from({length:10},(_,x)=>x===holes[Math.floor((19-y)/2)]?null:'G');
 const report={turns:0,attack:0,lines:0,quads:0,pcs:0,spins:0,fullSpins:0,holds:0,garbageCleared:0,maxCombo:0,maxB2B:0,maxHeight:0,topout:false},times=[];
 for(let turn=0;turn<turns;turn++){
  if(garbage&&turn&&turn%9===0){if(board.slice(0,2).some(r=>r.some(Boolean))){report.topout=true;break;}board=board.slice(2).concat(Array.from({length:2},()=>Array.from({length:10},(_,x)=>x===holes[turn/9]?null:'G')));}
  const piece=queue.shift(),s={board,piece,start:E.entry(piece,true),queue:queue.slice(0,5),hold,chain,simpleOnly:true,tucks:true,rotationSystem:'srs+',allow180:true,allowHold:true,canHold:true,profile:'versus',attackPriority:true};
  const at=performance.now(),c=choose(s,updated);times.push(performance.now()-at);
  if(!c||!c.nextSafe){report.topout=true;break;}
  let pos=c.useHold?E.entry(c.piece,true):s.start;
  for(const action of c.path){pos=E.move(board,c.piece,pos,action,'srs+');if(!pos)throw Error('Unreachable route');}
  if(JSON.stringify(E.lock(board,c.piece,pos).board)!==JSON.stringify(c.board))throw Error('Wrong result');
  if(c.useHold&&!hold)queue.shift();board=c.board;hold=c.newHold;
  const event=E.tactical(c,chain,'versus');chain={combo:event.combo,b2b:event.b2b};
  report.turns++;report.attack+=event.attackEstimate;report.lines+=c.lines;report.quads+=c.lines===4;
  report.pcs+=!!c.perfectClear;report.spins+=!!c.spin&&c.lines>0;report.fullSpins+=c.spin==='full'&&c.lines>0;
  report.holds+=!!c.useHold;report.garbageCleared+=c.garbageCleared||0;
  report.maxCombo=Math.max(report.maxCombo,chain.combo);report.maxB2B=Math.max(report.maxB2B,chain.b2b);report.maxHeight=Math.max(report.maxHeight,E.metrics(board).height);
 }
 times.sort((a,b)=>a-b);return {...report,attackPerPiece:+(report.attack/Math.max(1,report.turns)).toFixed(3),meanMs:+(times.reduce((a,b)=>a+b,0)/times.length).toFixed(2),p95Ms:+times[Math.floor(times.length*.95)].toFixed(2)};
}
const results=[];
for(const garbage of [false,true])for(const seed of seeds){
 const row={garbage,seed,before:run(seed,false,garbage),after:run(seed,true,garbage)};results.push(row);console.log(JSON.stringify(row));
 fs.writeFileSync(output,JSON.stringify({baseline,node:process.version,turnsPerRun:turns,seeds,model:'full-refinement, five previews, fixed garbage, ideal routes; no cancellation, timing or opponent',results},null,2)+'\n');
}
