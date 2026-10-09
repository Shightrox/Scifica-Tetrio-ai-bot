/* Deterministic, reachable-placement Tetris planner. No network or dependencies. */
(function (root) {
  'use strict';
  const W=10,H=20;
  const BASE={T:[[1,0],[0,1],[1,1],[2,1]],I:[[0,1],[1,1],[2,1],[3,1]],O:[[0,0],[1,0],[0,1],[1,1]],S:[[1,0],[2,0],[0,1],[1,1]],Z:[[0,0],[1,0],[1,1],[2,1]],J:[[0,0],[0,1],[1,1],[2,1]],L:[[2,0],[0,1],[1,1],[2,1]]};
  const KICKS={
    '0>1':[[0,0],[-1,0],[-1,1],[0,-2],[-1,-2]],'1>0':[[0,0],[1,0],[1,-1],[0,2],[1,2]],
    '1>2':[[0,0],[1,0],[1,-1],[0,2],[1,2]],'2>1':[[0,0],[-1,0],[-1,1],[0,-2],[-1,-2]],
    '2>3':[[0,0],[1,0],[1,1],[0,-2],[1,-2]],'3>2':[[0,0],[-1,0],[-1,-1],[0,2],[-1,2]],
    '3>0':[[0,0],[-1,0],[-1,-1],[0,2],[-1,2]],'0>3':[[0,0],[1,0],[1,1],[0,-2],[1,-2]]
  };
  const IK={
    '0>1':[[0,0],[-2,0],[1,0],[-2,-1],[1,2]],'1>0':[[0,0],[2,0],[-1,0],[2,1],[-1,-2]],
    '1>2':[[0,0],[-1,0],[2,0],[-1,2],[2,-1]],'2>1':[[0,0],[1,0],[-2,0],[1,-2],[-2,1]],
    '2>3':[[0,0],[2,0],[-1,0],[2,1],[-1,-2]],'3>2':[[0,0],[-2,0],[1,0],[-2,-1],[1,2]],
    '3>0':[[0,0],[1,0],[-2,0],[1,-2],[-2,1]],'0>3':[[0,0],[-1,0],[2,0],[-1,2],[2,-1]]
  };
  function cells(t,r=0){let c=BASE[t].map(p=>p.slice());if(t==='O')return c;const n=t==='I'?3:2;for(let i=0;i<r;i++)c=c.map(([x,y])=>[n-y,x]);return c;}
  const SHAPES=Object.fromEntries(Object.keys(BASE).map(t=>[t,[0,1,2,3].map(r=>cells(t,r))]));
  const empty=()=>Array.from({length:H},()=>Array(W).fill(null));
  const clone=b=>b.map(r=>r.slice());
  const spawn=t=>({x:t==='O'?4:3,y:0,r:0});
  function fits(b,t,p){return SHAPES[t][p.r].every(([dx,dy])=>{const x=p.x+dx,y=p.y+dy;return x>=0&&x<W&&y>=-3&&y<H&&(y<0||!b[y][x]);});}
  function move(b,t,p,a){let n={...p};if(a==='L')n.x--;else if(a==='R')n.x++;else if(a==='D')n.y++;else {
    if(t==='O')return null;n.r=(p.r+(a==='CW'?1:3))%4;
    for(const [dx,dy] of (t==='I'?IK:KICKS)[p.r+'>'+n.r]){const k={...n,x:p.x+dx,y:p.y-dy};if(fits(b,t,k))return k;}return null;
  }return fits(b,t,n)?n:null;}
  function lock(b,t,p){const out=clone(b);for(const [dx,dy] of SHAPES[t][p.r]){const y=p.y+dy,x=p.x+dx;if(y<0)return null;out[y][x]=t;}const garbageCleared=out.filter(r=>r.every(Boolean)&&r.includes('G')).length;const kept=out.filter(r=>r.some(v=>!v)),lines=H-kept.length;while(kept.length<H)kept.unshift(Array(W).fill(null));return {board:kept,lines,garbageCleared};}
  function metrics(b){
    let holes=0,buried=0,garbageCover=0,roughness=0;const heights=[],holeCells=[];
    const garbage=b.map(r=>r.filter(v=>v==='G').length>=8);
    for(let x=0;x<W;x++){let top=H,cover=0,coloredCover=0;
      for(let y=0;y<H;y++){
        if(b[y][x]){top=Math.min(top,y);cover++;if(b[y][x]!=='G')coloredCover++;}
        else {if(cover){holes++;buried+=cover;holeCells.push([x,y]);}if(garbage[y])garbageCover+=coloredCover;}
      }heights.push(H-top);
    }
    let well=0;for(let x=1;x<W;x++)if(heights[x]<heights[well])well=x;
    let wellDepth=0;for(let y=H-heights[well]-1;y>=0;y--){if(!b[y].every((v,x)=>x===well||v))break;wellDepth++;}
    let bump=0;for(let x=1;x<W;x++){const d=Math.abs(heights[x]-heights[x-1]);bump+=d;if(!wellDepth||x!==well&&x-1!==well)roughness+=d*d;}
    const center=Math.max(...heights.slice(3,7));
    return {holes,buried,heights,holeCells,bump,roughness,garbageCover,well,wellDepth,center,height:Math.max(...heights),total:heights.reduce((a,b)=>a+b,0)};
  }
  function utility(m,lines){return lines*9-m.total*.44-m.holes*13-m.buried*.7-m.bump*.25-m.roughness*.18-m.garbageCover*2.5
    -Math.max(0,m.height-10)**2*1.6-Math.max(0,m.height-15)**2*5-Math.max(0,m.center-13)**2*2;}
  function autoPolicy(m){
    const danger=m.height>=13||m.garbageCover>=8||m.holes>=6;
    const constrained=m.height>=9||m.garbageCover>=2||m.holes>=2;
    const mode=danger?'survive':constrained?'balance':'attack';
    const reason=m.height>=13?'height':m.garbageCover>=8?'garbage':m.holes>=6?'holes':constrained?'space':'room';
    return {mode,reason};
  }
  function setupPotential(m,queue,hold,allowHold){
    // Reward a usable, open quad well only when a known I is available soon.
    // Capping at four rows avoids paying for arbitrarily tall towers. Dirty
    // stacks and survival positions earn nothing for banking more rows.
    const mode=autoPolicy(m).mode;
    if(mode==='survive'||m.holes||m.garbageCover)return 0;
    const at=queue.indexOf('I');
    const availability=allowHold&&hold==='I'?1:at>=0&&at<4?Math.pow(.8,at+1):0;
    if(!availability)return 0;
    // The surface profile also values partly completed layers around the well.
    // Without this term the search greedily skims singles before it can build
    // the first complete nine-cell row of a future quad.
    let potential=0;const weights=[14,14,14,10],base=m.heights[m.well];
    for(let d=1;d<=4;d++){
      const filled=m.heights.filter((h,x)=>x!==m.well&&h>=base+d).length;
      potential+=weights[d-1]*Math.pow(filled/9,4);
    }
    return potential*availability*(mode==='attack'?1:.4);
  }
  function positionValue(m,queue,hold,allowHold,profile){
    return utility(m,0)+(profile==='versus'?setupPotential(m,queue,hold,allowHold):0);
  }
  const entry=(t,simple)=>simple?{...spawn(t),y:-2}:spawn(t);
  function placements(board,t,start=spawn(t),simpleOnly=false,firstOnly=false){
    if(!fits(board,t,start))return [];const nodes=[{...start,parent:-1,a:null}],visited=new Set([`${start.x},${start.y},${start.r}`]),landed=new Set(),out=[];
    for(let i=0;i<nodes.length;i++){const origin=nodes[i];let p=origin;if(simpleOnly){p={...origin};while(move(board,t,p,'D'))p=move(board,t,p,'D');}if(simpleOnly||!move(board,t,p,'D')){
      const id=SHAPES[t][p.r].map(([dx,dy])=>(p.y+dy)*W+p.x+dx).sort((a,b)=>a-b).join(',');
      if(!landed.has(id)){landed.add(id);const locked=lock(board,t,p);if(locked){if(firstOnly)return [locked];let path=[],at=i;while(nodes[at].parent!==-1){path.push(nodes[at].a);at=nodes[at].parent;}path.reverse();if(simpleOnly)path.push(...Array(p.y-origin.y).fill('D'));const m=metrics(locked.board);out.push({piece:t,pos:{x:p.x,y:p.y,r:p.r},path,board:locked.board,lines:locked.lines,garbageCleared:locked.garbageCleared,metrics:m,score:utility(m,locked.lines),perfectClear:locked.board.every(r=>r.every(v=>!v))});}}
    }
    for(const a of (simpleOnly?['L','R','CW','CCW']:['L','R','CW','CCW','D'])){const n=move(board,t,origin,a);if(!n)continue;const k=`${n.x},${n.y},${n.r}`;if(visited.has(k))continue;visited.add(k);nodes.push({...n,parent:i,a});}}
    return out.sort((a,b)=>b.score-a.score||a.path.length-b.path.length);
  }
  // Private rooms can customize attack rules. This is a strategic reward,
  // not a claim to reproduce exact damage, spins or incoming cancellation.
  function tactical(c,chain={combo:0,b2b:0},profile='classic'){
    const combo=c.lines?(chain.combo||0)+1:0;
    const difficult=c.lines>0&&(c.lines===4||c.perfectClear);
    const b2b=difficult?(chain.b2b||0)+1:c.lines?0:(chain.b2b||0);
    const comboIndex=Math.max(0,combo-1);
    const base=[0,0,1,2,4][c.lines]+(difficult&&chain.b2b?1:0);
    // Include the combo floor: a chain of singles is not always zero attack.
    // PC and Surge are separate additions, outside the combo multiplier.
    const attack=c.lines?Math.floor(Math.max(base*(1+.25*comboIndex),Math.log1p(1.25*comboIndex))):0;
    const surge=c.lines&&!difficult&&(chain.b2b||0)>=4?chain.b2b:0;
    const bonus=8*attack+Math.min(12,Math.max(0,combo-1)*2)+(c.perfectClear?40:0)+surge*6+(c.garbageCleared||0)*4;
    return {reward:profile==='versus'?5*c.lines+bonus:9*c.lines,combo,b2b,attackEstimate:attack+(c.perfectClear?5:0)+surge};
  }
  function choices(board,piece,queue,hold,start,simpleOnly,canHold){
    const out=placements(board,piece,start||entry(piece,simpleOnly),simpleOnly).map(c=>({...c,useHold:false,nextQueue:queue.slice(),newHold:hold}));
    if(canHold&&(hold||queue.length)){
      const t=hold||queue[0],q=hold?queue:queue.slice(1);
      // Identical-piece swaps cannot improve the reachable straight-drop set.
      if(t!==piece)out.push(...placements(board,t,entry(t,simpleOnly),simpleOnly).map(c=>({...c,useHold:true,nextQueue:q.slice(),newHold:piece})));
    }
    return out;
  }
  function evaluate(c,before,chain,profile,simpleOnly,allowHold,attackPriority=false){
    c.chain=tactical(c,chain,profile);
    const m=c.metrics;c.auto=autoPolicy(before);c.attackPriority=!!attackPriority;
    const danger=c.auto.mode==='survive',attack=c.auto.mode==='attack';
    const damage=c.chain.reward-5*c.lines;
    const newHoles=Math.max(0,m.holes-before.holes),newCover=Math.max(0,m.garbageCover-before.garbageCover);
    c.stepReward=profile==='versus'?(danger?8:5)*c.lines+damage*(danger?.55:attack?1.3:1.1):c.chain.reward;
    const pressure=attackPriority&&profile==='versus'&&!danger;
    if(pressure)c.stepReward+=c.chain.attackEstimate*(attack?12:6)-2*c.lines;
    if(profile==='versus'&&!danger&&c.lines&&chain.combo)c.stepReward+=Math.min(12,4+chain.combo*2)*(attack?1:.5);
    // These costs apply to every intermediate board, not just the search leaf.
    c.stepReward-=newHoles*8+Math.max(0,m.buried-before.buried)*.5+newCover*3;
    if(danger)c.stepReward-=Math.max(0,m.height-before.height)*5;
    c.stepReward-=c.path.filter(a=>a!=='D').length*(danger?.45:attack?.12:.18);
    c.nextSafe=true;
    if(c.nextQueue.length&&m.height>=16){
      const next=c.nextQueue[0],held=c.newHold||c.nextQueue[1];
      c.nextSafe=placements(c.board,next,entry(next,simpleOnly),simpleOnly,true).length>0
        ||!!(allowHold&&held&&placements(c.board,held,entry(held,simpleOnly),simpleOnly,true).length);
    }
    c.safety=danger?'downstack':'balanced';
    c.setup=profile==='versus'?setupPotential(m,c.nextQueue,c.newHold,allowHold):0;
    c.terminal=positionValue(m,c.nextQueue,c.newHold,allowHold,profile);
    if(pressure){
      // Value a banked B2B chain once at the leaf, not on every empty lock.
      // A second deep, narrow well competes for the I needed to attack.
      const forcedI=m.heights.reduce((n,h,x)=>n+(x===m.well?0:Math.max(0,Math.min(x?m.heights[x-1]:H,x<W-1?m.heights[x+1]:H)-h-2)),0);
      c.terminal+=Math.min(8,c.chain.b2b)*2-forcedI*4;
    }
    c.score=c.terminal+c.stepReward+(c.nextSafe?0:-1000000);
    return c;
  }
  function analyze({board,piece,queue=[],hold=null,start=null,depth=2,allowHold=true,canHold=true,rootLimit=12,beamWidth=5,simpleOnly=false,profile='classic',chain={combo:0,b2b:0},attackPriority=false}){
    const before=metrics(board);
    const options=choices(board,piece,queue,hold,start,simpleOnly,allowHold&&canHold);
    for(const c of options)evaluate(c,before,chain,profile,simpleOnly,allowHold,attackPriority);
    options.sort((a,b)=>b.score-a.score);
    const roots=options.slice(0,rootLimit),total=options.length;
    // Preserve at least one alternative from both HOLD branches when pruning.
    if(allowHold&&canHold&&roots.length>1)for(const h of [false,true]){
      const c=options.find(c=>c.useHold===h);if(c&&!roots.some(r=>r.useHold===h))roots[roots.length-1]=c;
    }
    // A preparation move may rank below several nearly identical immediate
    // clears. Let the existing lookahead compare one such branch explicitly.
    if(profile==='versus'&&autoPolicy(before).mode!=='survive'&&roots.length>=4){
      const setup=options.filter(c=>c.nextSafe&&c.setup>0).sort((a,b)=>b.setup-a.setup||b.score-a.score)[0];
      if(setup&&!roots.includes(setup)){
        const i=roots.findLastIndex((r,i)=>i>0&&roots.filter(c=>c.useHold===r.useHold).length>1);
        if(i>0)roots[i]=setup;
      }
    }
    for(const c of roots){
      let beam=c.nextSafe?[{board:c.board,value:c.stepReward,terminal:c.terminal,chain:c.chain,future:[],queue:c.nextQueue,hold:c.newHold}]:[],effective=1;
      for(let d=1;d<depth;d++){
        const next=[];
        for(const state of beam){
          if(!state.queue.length){next.push({...state,rank:state.value+state.terminal});continue;}
          const ps=choices(state.board,state.queue[0],state.queue.slice(1),state.hold,null,simpleOnly,allowHold);
          const previous=metrics(state.board);
          for(const p of ps){evaluate(p,previous,state.chain,profile,simpleOnly,allowHold,attackPriority);p.rank=p.score;}
          ps.sort((a,b)=>b.rank-a.rank);
          for(const p of ps.slice(0,beamWidth)){
            if(!p.nextSafe)continue;
            const value=state.value+p.stepReward*Math.pow(.9,d);
            next.push({board:p.board,value,terminal:p.terminal,chain:p.chain,queue:p.nextQueue,hold:p.newHold,
              future:[...state.future,{piece:p.piece,pos:p.pos,board:p.board,lines:p.lines,useHold:p.useHold,perfectClear:p.perfectClear,combo:p.chain.combo,b2b:p.chain.b2b,attackEstimate:p.chain.attackEstimate}],rank:value+p.terminal});
          }
        }
        if(!next.length){beam=[];break;}
        beam=next.sort((a,b)=>b.rank-a.rank).slice(0,beamWidth);effective=1+beam[0].future.length;
      }
      c.lookahead=effective;c.future=beam[0]?.future||[];c.value=beam.length?beam[0].value+beam[0].terminal:-1000000+c.score;
      const sequence=[c,...c.future];let run=chain.combo||0,best=run;
      for(const p of sequence){run=p.lines?run+1:0;best=Math.max(best,run);}
      c.intent=c.auto.mode==='survive'?'downstack':sequence.some(p=>p.perfectClear)?'perfect-clear'
        :best>=Math.max(2,(chain.combo||0)+1)?'combo':sequence.some(p=>p.lines===4)?'quad'
        :c.setup>=8?'prepare-quad':'clean-stack';
      c.comboPlan=best;
      c.attackPlan=c.chain.attackEstimate+c.future.reduce((sum,p)=>sum+p.attackEstimate,0);
      c.attackPerPiece=c.attackPlan/c.lookahead;
      if(attackPriority&&profile==='versus'&&c.auto.mode!=='survive')c.value+=c.attackPerPiece*10;
    }
    roots.sort((a,b)=>b.value-a.value||Number(a.useHold)-Number(b.useHold)||a.path.length-b.path.length);
    return {candidates:roots.slice(0,3),total,before};
  }
  const api={W,H,BASE,SHAPES,empty,clone,spawn,entry,fits,move,lock,metrics,placements,analyze,tactical,autoPolicy,setupPotential,choices,evaluate};
  if(typeof module!=='undefined')module.exports=api;root.Tetris=api;
})(typeof self!=='undefined'?self:globalThis);
