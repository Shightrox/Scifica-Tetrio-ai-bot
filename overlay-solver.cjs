const {Worker,isMainThread,parentPort}=require('node:worker_threads');
const E=require('./engine.js');
const PC=require('./perfect-clear.cjs');
const family=s=>JSON.stringify([s.board,s.piece,s.queue,s.hold||null,!!s.allowHold,s.canHold!==false,!!s.simpleOnly,s.profile||'classic',s.chain||{combo:0,b2b:0},!!s.attackPriority]);
if(!isMainThread){
  // Warm worker: no process startup or termination per falling piece/frame.
  parentPort.on('message',m=>{
    const at=performance.now();
    try{
      const pressure=m.state.attackPriority&&m.state.profile==='versus';
      const pc=pressure?PC.find(m.state):null;
      let result,continuation=null;
      if(pc?.sequence){
        result=E.analyze({...m.state,depth:1});
        const c=pc.sequence[0].candidate;
        if(c.value>=result.candidates[0]?.value){
          result.candidates=[c,...result.candidates.filter(p=>p.useHold!==c.useHold||JSON.stringify(p.pos)!==JSON.stringify(c.pos))].slice(0,3);
          continuation=pc.sequence;
        }else result=null;
      }
      if(!result)result=E.analyze({...m.state,depth:pressure?4:3,rootLimit:pressure?6:8,beamWidth:3});
      if(pc)result.pcSearch={status:pc.status,nodes:pc.nodes,ms:pc.ms};
      parentPort.postMessage({key:m.key,result,continuation,ms:performance.now()-at});
    }
    catch(error){parentPort.postMessage({key:m.key,error:String(error)});}
  });
}else{
  const readline=require('node:readline');
  let latest=null,busy=null,pending=null;
  let continuations=[];
  const cache=new Map();
  const proofs=new Map();
  const background=new Worker(__filename);
  const emit=v=>process.stdout.write(JSON.stringify(v)+'\n');
  const shapeKey=c=>c.piece+':'+E.SHAPES[c.piece][c.pos.r].map(([x,y])=>(y+c.pos.y)*10+x+c.pos.x).sort((a,b)=>a-b).join(',');
  function rebase(result,state){
    const reachable=new Map(E.placements(state.board,state.piece,state.start,!!state.simpleOnly).map(c=>[shapeKey(c),c]));
    let held=null;
    const candidates=result.candidates.map(c=>{
      if(c.useHold){
        if(!state.allowHold||state.canHold===false||c.piece!==(state.hold||state.queue[0]))return null;
        if(!held)held=new Map(E.placements(state.board,c.piece,E.entry(c.piece,!!state.simpleOnly),!!state.simpleOnly).map(p=>[shapeKey(p),p]));
        const p=held.get(shapeKey(c));return p?{...c,pos:p.pos,path:p.path,nextQueue:state.hold?state.queue.slice():state.queue.slice(1),newHold:state.piece}:null;
      }
      const p=reachable.get(shapeKey(c));return p?{...c,pos:p.pos,path:p.path,nextQueue:state.queue.slice(),newHold:state.hold}:null;
    }).filter(Boolean);
    return candidates.length?{...result,candidates}:null;
  }
  function store(key,result,proof){
    cache.delete(key);cache.set(key,result);if(proof)proofs.set(key,proof);else proofs.delete(key);
    while(cache.size>64){const old=cache.keys().next().value;cache.delete(old);proofs.delete(old);}
  }
  function remember(sequence){
    continuations=[];
    for(const {state,candidate} of sequence){
      continuations.push({state,candidate});
      if(candidate.useHold)continuations.push({
        state:{...state,piece:candidate.piece,hold:state.piece,queue:candidate.nextQueue,canHold:false},
        candidate:{...candidate,useHold:false}
      });
    }
  }
  function continuation(state){
    if(!state.attackPriority){continuations=[];return null;}
    for(const item of continuations){
      const s=item.state;
      if(s.piece!==state.piece||(s.hold||null)!==(state.hold||null)||s.profile!==state.profile||
        !!s.allowHold!==!!state.allowHold||(s.canHold!==false)!==(state.canHold!==false)||
        !!s.simpleOnly!==!!state.simpleOnly||JSON.stringify(s.board)!==JSON.stringify(state.board)||
        (s.chain?.combo||0)!==(state.chain?.combo||0)||(s.chain?.b2b||0)!==(state.chain?.b2b||0)||
        s.queue.some((t,i)=>t!==state.queue[i]))continue;
      // Newly revealed preview tails cannot invalidate a proved path that only
      // used its known prefix. Still reroute from the actually observed pose.
      const result=rebase({candidates:[item.candidate],total:1,before:E.metrics(state.board)},state);
      if(result)return result;
    }
    return null;
  }
  function dispatch(){if(busy||!pending)return;busy=pending;pending=null;background.postMessage(busy);}
  function deepen(state,key){
    if(cache.has(key))return;
    if(busy?.key===key){pending=null;return;}
    pending={state,key};dispatch();
  }
  background.on('message',m=>{
    const completed=busy;busy=null;
    if(m.result)store(m.key,m.result,m.continuation);
    if(m.continuation&&latest?.key===m.key)remember(m.continuation);
    if(latest?.key===m.key){
      const result=continuation(latest.state)||(m.result&&rebase(m.result,latest.state));
      emit(result?{id:latest.id,stage:'final',result,cache:false,ms:m.ms}:{id:latest.id,stage:'done',detail:m.error});
    }
    // One predicted position, only when no real position is waiting.
    if(!pending&&completed&&latest?.key===m.key&&m.result?.candidates.length){
      const c=m.result.candidates[0],q=c.nextQueue;
      if(q.length){const state={...completed.state,board:c.board,piece:q[0],queue:q.slice(1),hold:c.newHold,canHold:true,start:{...E.spawn(q[0]),y:-2},chain:{combo:c.chain.combo,b2b:c.chain.b2b}};
        const key=family(state);if(!cache.has(key))pending={state,key};}
    }
    dispatch();
  });
  background.on('error',error=>{busy=null;pending=null;if(latest)emit({id:latest.id,stage:'done',detail:String(error)});});
  readline.createInterface({input:process.stdin}).on('line',line=>{
    let m;
    try{
      m=JSON.parse(line);const at=performance.now(),state={...m.state,allowHold:!!m.state.allowHold},key=family(state);
      latest={id:m.id,at,state,key};
      const planned=continuation(state);
      if(planned){pending=null;emit({id:m.id,stage:'final',cache:true,continuation:true,result:planned,ms:performance.now()-at});return;}
      const hit=cache.get(key),cached=hit&&rebase(hit,state);
      if(cached){if(proofs.has(key))remember(proofs.get(key));pending=null;emit({id:m.id,stage:'final',cache:true,result:cached,ms:performance.now()-at});return;}
      const quick=E.analyze({...state,depth:1});
      emit({id:m.id,stage:'fast',result:quick,cache:false,ms:performance.now()-at});
      if(state.queue.length&&m.refine!==false)deepen(state,key);
      else emit({id:m.id,stage:'done'});
    }catch(error){emit({id:m?.id,stage:'error',error:String(error)});}
  }).on('close',()=>background.terminate());
}
