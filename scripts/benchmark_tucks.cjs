// Seeded planner comparison with v0.16.1; ideal execution, no game input.
const fs=require('node:fs'),path=require('node:path'),{execFileSync}=require('node:child_process');
const E=require('../engine'),PC=require('../perfect-clear.cjs'),Attack=require('../attack-search.cjs');
const baseline='00dd1fae87e43e226836aa75556af8716a9f9c55',root=path.join(__dirname,'..');
function historical(file,imports){const m={exports:{}};new Function('module','require',execFileSync('git',['show',baseline+':'+file],{cwd:root,encoding:'utf8'}))(m,imports);return m.exports;}
const old=historical('engine.js',require),oldPC=historical('perfect-clear.cjs',id=>id==='./engine.js'?old:require(id));globalThis.Tetris=E;
const output=path.resolve(process.argv[2]||'work/tucks-results.json');fs.mkdirSync(path.dirname(output),{recursive:true});
function run(seed,updated,garbage){
 const rng=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296),queue=[];
 while(queue.length<250){const bag=[...'IOTSZJL'];for(let i=6;i;i--){const j=Math.floor(rng()*(i+1));[bag[i],bag[j]]=[bag[j],bag[i]];}queue.push(...bag);}
 const holes=Array.from({length:40},()=>Math.floor(rng()*10));let board=E.empty(),hold=null,chain={combo:0,b2b:0},proof=[];
 const engine=updated?E:old,pcEngine=updated?PC:oldPC;
 if(garbage)for(let y=12;y<20;y++)board[y]=Array.from({length:10},(_,x)=>x===holes[Math.floor((19-y)/2)]?null:'G');
 const report={turns:0,attack:0,lines:0,quads:0,pcs:0,spins:0,holds:0,maxCombo:0,maxB2B:0,maxHeight:0};const times=[];
 for(let turn=0;turn<60;turn++){
  if(garbage&&turn&&turn%7===0){if(board.slice(0,2).some(r=>r.some(Boolean)))break;board=board.slice(2).concat(Array.from({length:2},()=>Array.from({length:10},(_,x)=>x===holes[turn/7]?null:'G')));proof=[];}
  const piece=queue.shift(),s={board,piece,start:E.entry(piece,true),queue:queue.slice(0,5),hold,chain,simpleOnly:true,tucks:updated,allowHold:true,canHold:true,profile:'versus',attackPriority:true};
  const at=performance.now();let c;
  if(proof.length){const first=proof.shift();if(first.state.piece===piece&&JSON.stringify(first.state.board)===JSON.stringify(board))c=first.candidate;else proof=[];}
  if(!c){
   const pc=pcEngine.find(s);if(pc.sequence){const quick=engine.analyze({...s,depth:1});if(pc.sequence[0].candidate.value>=quick.candidates[0]?.value){proof=pc.sequence;c=proof.shift().candidate;}}
   if(!c){c=engine.analyze({...s,depth:updated?6:4,rootLimit:6,beamWidth:3}).candidates[0];
    if(updated){const attack=Attack.find(s);if(attack.sequence?.[0].candidate.value>c?.value){proof=attack.sequence;c=proof.shift().candidate;}}
   }
  }
  times.push(performance.now()-at);if(!c||!c.nextSafe)break;
  let pos=c.useHold?E.entry(c.piece,true):s.start;for(const action of c.path){pos=E.move(board,c.piece,pos,action);if(!pos)throw Error('Unreachable route');}
  if(JSON.stringify(E.lock(board,c.piece,pos).board)!==JSON.stringify(c.board))throw Error('Wrong result');
  if(c.useHold&&!hold)queue.shift();board=c.board;hold=c.newHold;
  const event=E.tactical(c,chain,'versus');chain={combo:event.combo,b2b:event.b2b};
  report.turns++;report.attack+=event.attackEstimate;report.lines+=c.lines;report.quads+=c.lines===4;
  report.pcs+=!!c.perfectClear;report.spins+=!!c.spin&&c.lines>0;report.holds+=!!c.useHold;
  report.maxCombo=Math.max(report.maxCombo,chain.combo);report.maxB2B=Math.max(report.maxB2B,chain.b2b);report.maxHeight=Math.max(report.maxHeight,E.metrics(board).height);
 }
 times.sort((a,b)=>a-b);return {...report,meanMs:+(times.reduce((a,b)=>a+b,0)/times.length).toFixed(2),p95Ms:+times[Math.floor(times.length*.95)].toFixed(2)};
}
const results=[];
for(const garbage of [false,true])for(const seed of [7,19,31]){
 const row={garbage,seed,before:run(seed,false,garbage),after:run(seed,true,garbage)};results.push(row);console.log(JSON.stringify(row));
 fs.writeFileSync(output,JSON.stringify({baseline,node:process.version,turnsPerRun:60,seeds:[7,19,31],results},null,2)+'\n');
}
