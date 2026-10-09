// Offline planner comparison; no capture, networking or game input.
const fs=require('node:fs');
const path=require('node:path'),{execFileSync}=require('node:child_process');
const E=require('../engine.js'),PC=require('../perfect-clear.cjs');
const baseline='92a08bae90fecf9161e1144ecb3a0a2bc6a0405c'; // v0.15.2
// Both versions run in the same JS realm, avoiding cross-context VM overhead.
// The source is this repository's pinned historical commit, not remote code.
const baselineModule={exports:{}},previousGlobal=globalThis.Tetris;
new Function('module',execFileSync('git',['show',baseline+':engine.js'],{cwd:path.join(__dirname,'..'),encoding:'utf8'}))(baselineModule);
const old=baselineModule.exports;globalThis.Tetris=previousGlobal;
const destination=path.resolve(process.argv[2]||'work/pressure-results.json');
fs.mkdirSync(path.dirname(destination),{recursive:true});
function schedule(seed){const rng=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296),pieces=[];
 while(pieces.length<300){const bag=[...'IOTSZJL'];for(let i=6;i;i--){const j=Math.floor(rng()*(i+1));[bag[i],bag[j]]=[bag[j],bag[i]];}pieces.push(...bag);}
 return {pieces,holes:Array.from({length:60},()=>Math.floor(rng()*10))};}
function run(seed,pressure,garbage){
 const {pieces,holes}=schedule(seed);let board=E.empty(),queue=pieces.slice(),hold=null,chain={combo:0,b2b:0};
 let attack=0,lines=0,quads=0,pcs=0,maxHeight=0,turn=0,proof=[],pcHits=0;
 const times=[];
 if(garbage)for(let y=12;y<20;y++)board[y]=Array.from({length:10},(_,x)=>x===holes[Math.floor((19-y)/2)]?null:'G');
 for(;turn<100;turn++){
  if(garbage&&turn&&turn%7===0){if(board.slice(0,2).some(r=>r.some(Boolean)))break;board=board.slice(2).concat(Array.from({length:2},()=>Array.from({length:10},(_,x)=>x===holes[turn/7]?null:'G')));proof=[];}
  const piece=queue.shift(),s={board,piece,queue:queue.slice(0,5),hold,start:E.entry(piece,true),chain,allowHold:true,canHold:true,simpleOnly:true,profile:'versus',attackPriority:pressure};
  const at=performance.now();let c;
  if(pressure){
   if(proof.length){const first=proof[0];if(first.state.piece===piece&&JSON.stringify(first.state.board)===JSON.stringify(board)){c=first.candidate;proof.shift();}else proof=[];}
   if(!c){const pc=PC.find(s);if(pc.sequence){const fast=E.analyze({...s,depth:1});if(pc.sequence[0].candidate.value>=fast.candidates[0]?.value){proof=pc.sequence;c=proof.shift().candidate;pcHits++;}}}
   if(!c)c=E.analyze({...s,depth:4,rootLimit:6,beamWidth:3}).candidates[0];
  }else c=old.analyze({...s,depth:3,rootLimit:8,beamWidth:3}).candidates[0];
  times.push(performance.now()-at);if(!c||c.value<=-999999)break;
  let pos=c.useHold?E.entry(c.piece,true):s.start;
  for(const action of c.path){pos=E.move(board,c.piece,pos,action);if(!pos)throw Error('Unreachable route');}
  if(JSON.stringify(E.lock(board,c.piece,pos).board)!==JSON.stringify(c.board))throw Error('Wrong predicted board');
  if(c.useHold&&!hold)queue.shift();board=c.board;hold=c.newHold;
  const event=E.tactical(c,chain,'versus');attack+=event.attackEstimate;chain={combo:event.combo,b2b:event.b2b};
  lines+=c.lines;quads+=c.lines===4;pcs+=!!c.perfectClear;maxHeight=Math.max(maxHeight,E.metrics(board).height);
 }
 times.sort((a,b)=>a-b);return {turns:turn,attack,lines,quads,pcs,pcHits,maxHeight,meanMs:+(times.reduce((a,b)=>a+b,0)/times.length).toFixed(2),p95Ms:+times[Math.floor(times.length*.95)].toFixed(2)};
}
const results=[];
for(const garbage of [false,true])for(const seed of [7,19,31,53,79,101]){
 const row={garbage,seed,before:run(seed,false,garbage),after:run(seed,true,garbage)};
 results.push(row);console.log(JSON.stringify(row));
 fs.writeFileSync(destination,JSON.stringify({baseline,node:process.version,seeds:[7,19,31,53,79,101],turnsPerRun:100,pcBudgetMs:24,results},null,2)+'\n');
}
