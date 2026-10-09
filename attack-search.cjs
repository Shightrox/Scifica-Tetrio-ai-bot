// Bounded search for consecutive clears across the visible queue and HOLD.
const E=require('./engine.js');
function decorate(sequence){
  for(let i=0;i<sequence.length;i++){
    const tail=sequence.slice(i).map(item=>item.candidate),c=tail[0];
    c.future=tail.slice(1).map(p=>({piece:p.piece,pos:p.pos,board:p.board,lines:p.lines,useHold:p.useHold,
      spin:p.spin,perfectClear:p.perfectClear,combo:p.chain.combo,b2b:p.chain.b2b,attackEstimate:p.chain.attackEstimate}));
    c.lookahead=tail.length;c.comboPlan=Math.max(...tail.map(p=>p.chain.combo));c.clearChainVerified=true;
    c.attackPlan=tail.reduce((sum,p)=>sum+p.chain.attackEstimate,0);c.attackPerPiece=c.attackPlan/tail.length;
    c.intent=c.auto.mode==='survive'?'downstack':tail.some(p=>p.perfectClear)?'perfect-clear':tail.some(p=>p.spin==='full')?'t-spin':'combo';
    c.value=tail.reduce((sum,p,j)=>sum+p.stepReward*Math.pow(.9,j),0)+tail.at(-1).terminal;
    if(c.attackPriority&&c.auto.mode!=='survive')c.value+=c.attackPerPiece*10;
  }
  return sequence;
}
function find(state,{maxMs=32,maxNodes=140,maxPieces=6}={}){
  if(E.autoPolicy(E.metrics(state.board)).mode==='survive')return {nodes:0,sequence:null};
  const deadline=performance.now()+maxMs,limit=Math.min(maxPieces,1+state.queue.length);
  let nodes=0,best=null,bestValue=-Infinity;const seen=new Map();
  function visit(s,sequence,value){
    if(sequence.length>=limit||!s.piece||nodes>=maxNodes||performance.now()>deadline)return;
    const key=JSON.stringify([s.board,s.piece,s.queue,s.hold,s.canHold,s.chain]);
    if((seen.get(key)??-Infinity)>=value)return;seen.set(key,value);nodes++;
    const before=E.metrics(s.board);
    const candidates=E.choices(s.board,s.piece,s.queue,s.hold,s.start,s.simpleOnly,s.allowHold&&s.canHold!==false,s.tucks,s).filter(c=>c.lines);
    for(const c of candidates)E.evaluate(c,before,s.chain||{},s.profile,s.simpleOnly,s.allowHold,s.attackPriority,s.tucks,s);
    candidates.sort((a,b)=>b.score-a.score);
    // Keep both exchange branches even when several immediate clears tie.
    const branches=candidates.slice(0,4);
    for(const hold of [false,true]){const c=candidates.find(c=>c.useHold===hold);if(c&&!branches.includes(c))branches.push(c);}
    for(const c of branches){
      if(!c.nextSafe)continue;
      const next=[...sequence,{state:s,candidate:c}],discounted=value+c.stepReward*Math.pow(.9,sequence.length);
      const attack=next.reduce((sum,item)=>sum+item.candidate.chain.attackEstimate,0);
      const score=discounted+c.terminal+(next[0].candidate.auto.mode==='survive'?0:attack/next.length*10);
      if(next.length>=2&&score>bestValue){bestValue=score;best=next;}
      if(performance.now()>deadline)break;
      visit({...s,board:c.board,piece:c.nextQueue[0],queue:c.nextQueue.slice(1),hold:c.newHold,canHold:true,
        start:c.nextQueue.length?E.entry(c.nextQueue[0],s.simpleOnly):null,chain:{combo:c.chain.combo,b2b:c.chain.b2b}},next,discounted);
    }
  }
  visit(state,[],0);
  // Clone: shared prefix objects must not be mutated while comparing branches.
  return {nodes,sequence:best?decorate(structuredClone(best)):null};
}
module.exports={find};
