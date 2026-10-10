// League construction search: complete breadth layers, executable routes and
// queue-backed T-slot credit. No speculative bags or fixed opener commitment.
'use strict';
const E=require('./engine.js');

function spinReachable(board,target,rules){
  const start=E.entry('T',true),nodes=[{...start,kick:null,half:false}],seen=new Set();
  if(!E.fits(board,'T',start))return false;
  for(let i=0;i<nodes.length;i++){
    const p=nodes[i],key=[p.x,p.y,p.r,p.kick==null?0:p.kick===4&&!p.half?2:1].join(',');
    if(seen.has(key))continue;seen.add(key);
    if(p.x===target.x&&p.y===target.y&&p.r===target.r&&E.spinType(board,'T',p,p.kick,p.half)==='full')return true;
    for(const action of ['CW','CCW',...(rules.allow180?['180']:[]),'L','R','SD']){
      const rot=['CW','CCW','180'].includes(action)?E.rotation(board,'T',p,action,rules.rotationSystem):null;
      const next=rot?.pos||(!['CW','CCW','180'].includes(action)&&E.move(board,'T',p,action));
      if(next)nodes.push({...next,kick:rot?.kick??null,half:action==='180'});
    }
  }
  return false;
}

function tSlot(board,queue,hold,allowHold,rules={},cache=new WeakMap()){
  const distance=allowHold&&hold==='T'?0:queue.indexOf('T');
  if(distance<0||distance>3)return {credit:0};
  let found=cache.get(board);
  if(!found){
    const m=E.metrics(board);found={credit:0};
    if(E.autoPolicy(m).mode!=='survive'){
      const targets=[];
      for(let y=Math.max(0,20-m.height-2);y<19;y++)for(let x=-1;x<9;x++)for(let r=0;r<4;r++){
        const pos={x,y,r};
        if(!E.fits(board,'T',pos)||E.move(board,'T',pos,'D'))continue;
        const corners=[[0,0],[2,0],[2,2],[0,2]].filter(([dx,dy])=>x+dx<0||x+dx>=10||y+dy>=20||board[y+dy]?.[x+dx]).length;
        if(corners<2)continue;
        const full=E.spinType(board,'T',pos,0)==='full';
        const after=E.lock(board,'T',pos);if(!after)continue;
        const shape=E.SHAPES.T[r],rows=[...new Set(shape.map(([,dy])=>y+dy))];
        const missing=rows.map(row=>board[row].filter((v,col)=>!v&&!shape.some(([dx,dy])=>x+dx===col&&y+dy===row)).length);
        const remaining=missing.reduce((a,b)=>a+b,0);
        if(remaining>4||missing.some(n=>n>3))continue;
        const clean=E.metrics(after.board);
        // Credit useful, repayable cover, never a second layer of hidden debt.
        if(clean.holes>m.holes||clean.garbageAccess>m.garbageAccess)continue;
        const repaired=Math.min(3,Math.max(0,m.holes-clean.holes));
        const ready=full&&remaining===0;
        if(!ready&&m.holes>2)continue;
        const credit=ready?(after.lines>=2?38:14)+repaired*12:Math.max(0,18-remaining*3);
        targets.push({credit,pos,lines:after.lines,holesAfter:clean.holes,ready});
      }
      targets.sort((a,b)=>b.credit-a.credit);
      found=targets.find(t=>!t.ready||spinReachable(board,t.pos,rules))||found;
    }
    cache.set(board,found);
  }
  return {...found,credit:found.credit*Math.pow(.72,distance)};
}

function evaluate(c,before,s,rules,cache){
  E.evaluate(c,before,s.chain||{},s.profile,s.simpleOnly,s.allowHold,s.attackPriority,s.tucks,rules);
  c.league=true;
  if(c.auto.mode==='survive')return c;
  const slot=tSlot(c.board,c.nextQueue,c.newHold,s.allowHold,rules,cache);
  // Replace unverified shape-only credit; it must have a native spin entrance.
  c.terminal+=slot.credit-(c.spinSetup||0);c.spinSetup=slot.credit;c.tSlot=slot.credit?slot:null;
  // T is a scarce attack resource. This modest cost never applies to rescue,
  // garbage extraction, PCs or an actual full spin.
  if(c.piece==='T'&&c.spin!=='full'&&!c.perfectClear&&!c.garbageCleared)c.stepReward-=6;
  if((s.chain?.b2b||0)>0&&c.lines&&c.lines<4&&!c.spin&&!c.perfectClear&&!c.chain.surge
      &&!before.garbageRows&&before.height<9)c.stepReward-=10;
  c.score=c.terminal+c.stepReward+(c.nextSafe?0:-1000000);
  return c;
}

const future=c=>({piece:c.piece,pos:c.pos,board:c.board,lines:c.lines,useHold:c.useHold,spin:c.spin,
  perfectClear:c.perfectClear,combo:c.chain.combo,b2b:c.chain.b2b,attackEstimate:c.chain.attackEstimate});
function decorate(path,state){
  const sequence=path.map(c=>({...c})),c=sequence[0];
  c.future=sequence.slice(1).map(future);c.lookahead=sequence.length;c.league=true;
  c.attackPlan=sequence.reduce((sum,p)=>sum+p.chain.attackEstimate,0);c.attackPerPiece=c.attackPlan/sequence.length;
  c.comboPlan=Math.max(state.chain?.combo||0,...sequence.map(p=>p.chain.combo));
  c.value=sequence.reduce((sum,p,i)=>sum+p.stepReward*Math.pow(.9,i),0)+sequence.at(-1).terminal+(c.auto.mode==='survive'?0:c.attackPerPiece*10);
  c.intent=c.auto.mode==='survive'?'downstack':sequence.some(p=>p.perfectClear)?'perfect-clear'
    :sequence.some(p=>p.spin==='full')?'t-spin':c.comboPlan>=Math.max(2,(state.chain?.combo||0)+1)?'combo'
    :sequence.some(p=>p.lines===4)?'quad':c.spinSetup?'prepare-spin':c.setup>=8?'prepare-quad':'clean-stack';
  return c;
}
function select(nodes,width){
  nodes.sort((a,b)=>b.rank-a.rank);
  // Reserve a few competitive construction lanes, instead of filling the
  // entire beam with cosmetically different flat surfaces or immediate skims.
  const preparation=nodes.filter(n=>n.c.spinSetup>=8&&n.c.auto.mode!=='survive'&&n.rank>=nodes[0].rank-50)
    .sort((a,b)=>b.c.spinSetup-a.c.spinSetup||b.rank-a.rank).slice(0,Math.floor(width/6));
  const ordered=[...preparation,...nodes];
  const out=[],seen=new Set(),roots=new Map();
  for(const n of ordered){
    const key=JSON.stringify([n.c.board.map(r=>r.map(v=>v==='G'?2:v?1:0)),n.c.nextQueue,n.c.newHold,n.c.chain.combo,n.c.chain.b2b]);
    if(seen.has(key))continue;seen.add(key);
    // Do not let dozens of variants of a single immediate root crowd out
    // construction/HOLD alternatives before the next piece is examined.
    const root=n.root,count=roots.get(root)||0;
    if(count>=Math.max(2,Math.ceil(width/4)))continue;
    out.push(n);roots.set(root,count+1);if(out.length>=width)break;
  }
  return out.sort((a,b)=>b.rank-a.rank);
}
function find(state,{maxMs=450,maxDepth=6,width=24,onLayer,aborted=()=>false}={}){
  const at=performance.now(),deadline=at+maxMs,cache=new WeakMap(),before=E.metrics(state.board);
  const rules={...state,league:true,survival:E.autoPolicy(before).mode==='survive'};
  const roots=E.choices(state.board,state.piece,state.queue,state.hold,state.start,state.simpleOnly,state.allowHold&&state.canHold!==false,state.tucks,rules);
  for(const c of roots)evaluate(c,before,state,rules,cache);
  const start=roots.filter(c=>c.nextSafe).map((c,root)=>({c,root,path:[c],value:c.stepReward,rank:c.score}));
  let beam=select(start,width),complete=beam,budgetHit=false,nodes=1;
  for(let d=1;d<maxDepth;d++){
    const next=[];
    for(const node of beam){
      if(performance.now()>=deadline||aborted()){budgetHit=true;break;}
      const c=node.c;
      if(!c.nextQueue.length){next.push(node);continue;}
      const s={...state,board:c.board,piece:c.nextQueue[0],queue:c.nextQueue.slice(1),hold:c.newHold,chain:c.chain,canHold:true,start:null};
      const before=E.metrics(s.board);
      // Clean non-T construction needs no surface descent. Keep full movement
      // for T/HOLD-T and boards with cavities; the current root always has it.
      const native=s.tucks&&(s.piece==='T'||s.allowHold&&s.hold==='T'||before.holes>0);
      const options=E.choices(s.board,s.piece,s.queue,s.hold,null,s.simpleOnly,s.allowHold,native,rules);nodes++;
      for(const p of options){
        evaluate(p,before,s,rules,cache);if(!p.nextSafe)continue;
        const value=node.value+p.stepReward*Math.pow(.9,d);
        next.push({c:p,root:node.root,path:[...node.path,p],value,rank:value+p.terminal});
      }
    }
    // An incomplete layer must not compare unequal search horizons.
    if(budgetHit||!next.length)break;
    beam=select(next,width);complete=beam;
    if(onLayer)onLayer(result());
    if(beam.every(n=>!n.c.nextQueue.length))break;
  }
  function result(){
    const ranked=complete.map(n=>decorate(n.path,state)).sort((a,b)=>b.value-a.value),seen=new Set(),candidates=[];
    for(const c of ranked){const k=JSON.stringify([c.piece,c.useHold,c.pos,c.spin]);if(seen.has(k))continue;seen.add(k);candidates.push(c);if(candidates.length===3)break;}
    return {candidates,total:roots.length,before,budgetHit,search:{kind:'league',nodes,depth:candidates[0]?.lookahead||0,ms:performance.now()-at}};
  }
  return result();
}
module.exports={find,tSlot,spinReachable,evaluate,decorate};
