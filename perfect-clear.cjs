/* Bounded, straight-drop PC search over known NEXT/HOLD. No guessed bags. */
'use strict';
const E=require('./engine.js');
const FULL=(1<<E.W)-1;
const geometry=Object.fromEntries(Object.entries(E.SHAPES).map(([piece,rotations])=>{
  const seen=new Set(),shapes=[];
  rotations.forEach((cells,r)=>{
    const left=Math.min(...cells.map(p=>p[0])),top=Math.min(...cells.map(p=>p[1]));
    const bottom=Math.max(...cells.map(p=>p[1]));
    const points=cells.map(([x,y])=>[x-left,bottom-y]);
    const key=points.map(p=>p.join(',')).sort().join(';');
    if(seen.has(key))return;seen.add(key);
    shapes.push({r,left,top,bottom,points,width:Math.max(...points.map(p=>p[0]))+1});
  });
  return [piece,shapes];
}));

function bitmap(board){
  const rows=board.map(row=>row.reduce((bits,v,x)=>bits|(v?1<<x:0),0)).reverse();
  while(rows.length&&!rows.at(-1))rows.pop();return rows;
}
function drops(rows,piece,ceiling){
  const heights=Array(E.W).fill(0);
  rows.forEach((bits,y)=>{for(let x=0;x<E.W;x++)if(bits&(1<<x))heights[x]=y+1;});
  const out=[];
  for(const shape of geometry[piece])for(let x=0;x<=E.W-shape.width;x++){
    const bottom=Math.max(0,...shape.points.map(([dx,dy])=>heights[x+dx]-dy));
    if(shape.points.some(([,dy])=>bottom+dy>=ceiling))continue;
    const result=rows.slice();
    for(const [dx,dy] of shape.points){const y=bottom+dy;while(result.length<=y)result.push(0);result[y]|=1<<(x+dx);}
    const kept=result.filter(row=>row!==FULL),lines=result.length-kept.length;
    while(kept.length&&!kept.at(-1))kept.pop();
    out.push({rows:kept,lines,pos:{x:x-shape.left,y:E.H-1-bottom-shape.bottom,r:shape.r}});
  }
  return out.sort((a,b)=>a.rows.length-b.rows.length||b.lines-a.lines||a.pos.x-b.pos.x);
}
function options(piece,queue,hold,allowHold,canHold=true){
  const out=[{piece,queue,hold,useHold:false}];
  if(allowHold&&canHold&&(hold||queue.length)){
    const replacement=hold||queue[0];
    if(replacement!==piece)out.push({piece:replacement,queue:hold?queue:queue.slice(1),hold:piece,useHold:true});
  }
  return out;
}
const samePosition=(a,b,piece)=>{
  const key=p=>E.SHAPES[piece][p.r].map(([x,y])=>(p.y+y)*E.W+p.x+x).sort((x,y)=>x-y).join(',');
  return key(a)===key(b);
};

// Re-run the ordinary reachable-placement engine before trusting a bitboard
// solution. Return every intermediate request/candidate for continuation reuse.
function materialize(state,steps){
  let current={...state,queue:state.queue.slice()},sequence=[];
  for(const step of steps){
    const found=E.choices(current.board,current.piece,current.queue,current.hold,current.start,true,
      !!current.allowHold&&current.canHold!==false,false,current).find(c=>c.piece===step.piece&&c.useHold===step.useHold&&samePosition(c.pos,step.pos,c.piece));
    if(!found)return null;
    E.evaluate(found,E.metrics(current.board),current.chain||{},current.profile||'versus',true,!!current.allowHold,!!current.attackPriority,false,current);
    if(!found.nextSafe)return null;
    sequence.push({state:current,candidate:found});
    current={...current,board:found.board,piece:found.nextQueue[0],queue:found.nextQueue.slice(1),hold:found.newHold,
      start:found.nextQueue.length?E.entry(found.nextQueue[0],true):null,canHold:true,chain:{combo:found.chain.combo,b2b:found.chain.b2b}};
  }
  if(!sequence.at(-1)?.candidate.perfectClear)return null;
  for(let i=0;i<sequence.length;i++){
    const tail=sequence.slice(i).map(p=>p.candidate),c=tail[0];
    c.future=tail.slice(1).map(p=>({piece:p.piece,pos:p.pos,board:p.board,lines:p.lines,useHold:p.useHold,
      perfectClear:p.perfectClear,combo:p.chain.combo,b2b:p.chain.b2b,attackEstimate:p.chain.attackEstimate}));
    c.lookahead=tail.length;c.intent='perfect-clear';c.pcVerified=true;c.pcPieces=tail.length;
    c.attackPlan=tail.reduce((sum,p)=>sum+p.chain.attackEstimate,0);c.attackPerPiece=c.attackPlan/tail.length;
    c.comboPlan=Math.max(...tail.map(p=>p.chain.combo));
    c.value=tail.reduce((sum,p,j)=>sum+p.stepReward*Math.pow(.9,j),0)+tail.at(-1).terminal;
    if(state.attackPriority)c.value+=c.attackPerPiece*10;
  }
  return sequence;
}

function find(state,{maxMs=24,maxNodes=12000,maxPieces=6}={}){
  const started=performance.now(),deadline=started+Math.max(0,maxMs);
  const rows=bitmap(state.board),count=state.board.flat().filter(Boolean).length;
  const horizon=Math.min(maxPieces,1+(state.queue||[]).length);
  const report={status:'ineligible',nodes:0,ms:0,sequence:null};
  // PC feasibility has exact cell parity. This is a low-stack tactic; never
  // spend this budget on a high field that needs immediate downstacking.
  if(count%2||rows.length>6||!state.piece||horizon<1)return report;
  if(E.autoPolicy(E.metrics(state.board)).mode==='survive')return report;
  let timedOut=false;
  const roots=E.choices(state.board,state.piece,state.queue||[],state.hold,state.start,true,
    !!state.allowHold&&state.canHold!==false,false,state);
  const failed=new Set();
  function visit(rows,piece,queue,hold,remaining,ceiling){
    if(!remaining)return rows.length?null:[];
    if(!piece||rows.length>ceiling)return null;
    if(++report.nodes>maxNodes||performance.now()>=deadline){timedOut=true;return null;}
    const key=rows.join(',')+'|'+piece+queue.join('')+'|'+(hold||'-')+'|'+remaining;
    if(failed.has(key))return null;
    for(const branch of options(piece,queue,hold,!!state.allowHold)){
      for(const p of drops(rows,branch.piece,ceiling)){
        const next=visit(p.rows,branch.queue[0],branch.queue.slice(1),branch.hold,remaining-1,ceiling-p.lines);
        if(next)return [{piece:branch.piece,pos:p.pos,useHold:branch.useHold},...next];
        if(timedOut)return null;
      }
    }
    failed.add(key);return null;
  }
  report.status='exhausted';
  for(let n=1;n<=horizon;n++){
    const ceiling=(count+4*n)/E.W;
    if(!Number.isInteger(ceiling)||ceiling<rows.length||ceiling>6)continue;
    for(const root of roots){
      const nextRows=bitmap(root.board);
      if(nextRows.length>ceiling-root.lines)continue;
      const tail=visit(nextRows,root.nextQueue[0],root.nextQueue.slice(1),root.newHold,n-1,ceiling-root.lines);
      if(tail){
        const sequence=materialize(state,[{piece:root.piece,pos:root.pos,useHold:root.useHold},...tail]);
        if(sequence){report.sequence=sequence;report.status='solved';report.ms=performance.now()-started;return report;}
      }
      if(timedOut)break;
    }
    if(timedOut)break;
  }
  report.status=timedOut?'budget':report.status;report.ms=performance.now()-started;return report;
}
module.exports={find,materialize,bitmap,drops};
