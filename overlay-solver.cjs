const {Worker,isMainThread,parentPort}=require('node:worker_threads');
const E=require('./engine.js');
const PC=require('./perfect-clear.cjs');
const Attack=require('./attack-search.cjs');
const League=require('./league-search.cjs');
const resetHold=s=>s.allowHold&&s.canHold!==false&&(s.hold||s.queue?.[0])===s.piece&&s.start&&['x','y','r'].some(k=>s.start[k]!==E.entry(s.piece,!!s.simpleOnly)[k]);
const identity=s=>JSON.stringify([s.board,s.piece,s.hold||null,!!s.allowHold,s.canHold!==false,!!resetHold(s),!!s.simpleOnly,s.profile||'classic',s.chain||{combo:0,b2b:0},!!s.attackPriority,!!s.tucks,s.rotationSystem||'srs',!!s.allow180,!!s.start?.uncertain]);
const family=s=>JSON.stringify([identity(s),s.queue]);
if(!isMainThread){
  // Warm worker: no process startup or termination per falling piece/frame.
  parentPort.on('message',m=>{
    const at=performance.now();
    try{
      const pressure=m.state.attackPriority&&m.state.profile==='versus'&&E.autoPolicy(E.metrics(m.state.board)).mode!=='survive';
      const league=pressure&&m.state.tucks,aborted=()=>m.cancel&&Atomics.load(m.cancel,0)!==0;
      if(m.state.tucks&&!league)parentPort.postMessage({key:m.key,partial:true,result:E.analyze({...m.state,depth:2,rootLimit:4,beamWidth:2}),ms:performance.now()-at});
      const pc=pressure?PC.find(m.state):null;
      let result,continuation=null;
      if(league)result=League.find(m.state,{aborted,onLayer:result=>{
        if(!aborted())parentPort.postMessage({key:m.key,partial:true,result,ms:performance.now()-at});
      }});
      if(pc?.sequence){
        result=result||E.analyze({...m.state,depth:1});
        const c=pc.sequence[0].candidate;
        if(c.value>=result.candidates[0]?.value){
          result.candidates=[c,...result.candidates.filter(p=>p.useHold!==c.useHold||JSON.stringify(p.pos)!==JSON.stringify(c.pos))].slice(0,3);
          continuation=pc.sequence;
        }else if(!league)result=null;
      }
      if(aborted()){parentPort.postMessage({key:m.key,aborted:true});return;}
      if(!result)result=E.analyze({...m.state,depth:pressure?(m.state.tucks?6:4):3,rootLimit:pressure?6:8,beamWidth:3,maxMs:pressure?140:90});
      if(pressure&&!continuation){
        const chain=Attack.find(m.state),c=chain.sequence?.[0].candidate;
        if(c&&c.value>result.candidates[0]?.value){
          result.candidates=[c,...result.candidates.filter(p=>p.useHold!==c.useHold||JSON.stringify(p.pos)!==JSON.stringify(c.pos))].slice(0,3);
          continuation=chain.sequence;
        }
      }
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
  const contexts=new Map();
  let background=null,closing=false,restartTimer=null,watchdog=null;
  const emit=v=>process.stdout.write(JSON.stringify(v)+'\n');
  const shapeKey=c=>c.piece+':'+E.SHAPES[c.piece][c.pos.r].map(([x,y])=>(y+c.pos.y)*10+x+c.pos.x).sort((a,b)=>a-b).join(',')+':'+(c.spin||'');
  function rerouted(c,p){
    const weight=c.auto?.mode==='survive'?.12:c.auto?.mode==='attack'?.3:.45;
    const adjustment=((c.routeCost||0)-(p.routeCost||0))*weight;
    return {...c,pos:p.pos,path:p.path,route:p.route,requiresSoftDrop:p.requiresSoftDrop,routeCost:p.routeCost,surfaceDescents:p.surfaceDescents,
      value:c.value+adjustment,score:c.score+adjustment,stepReward:c.stepReward+adjustment};
  }
  function rebase(result,state){
    const reachable=new Map(E.placements(state.board,state.piece,state.start,!!state.simpleOnly,false,!!state.tucks,state).map(c=>[shapeKey(c),c]));
    let held=null;
    const candidates=result.candidates.map(c=>{
      if(c.useHold){
        if(!state.allowHold||state.canHold===false||c.piece!==(state.hold||state.queue[0]))return null;
        if(!held)held=new Map(E.placements(state.board,c.piece,E.entry(c.piece,!!state.simpleOnly),!!state.simpleOnly,false,!!state.tucks,state).map(p=>[shapeKey(p),p]));
        const p=held.get(shapeKey(c));return p?{...rerouted(c,p),nextQueue:state.hold?state.queue.slice():state.queue.slice(1),newHold:state.piece}:null;
      }
      const p=reachable.get(shapeKey(c));return p?{...rerouted(c,p),nextQueue:state.queue.slice(),newHold:state.hold}:null;
    }).filter(Boolean);
    candidates.sort((a,b)=>b.value-a.value);
    return candidates.length?{...result,candidates,rebasedLost:candidates.length<result.candidates.length}:null;
  }
  function store(key,result,proof,state){
    cache.delete(key);cache.set(key,result);if(proof)proofs.set(key,proof);else proofs.delete(key);
    contexts.set(key,{identity:identity(state),queue:state.queue});
    while(cache.size>64){const old=cache.keys().next().value;cache.delete(old);proofs.delete(old);contexts.delete(old);}
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
    if(!state.attackPriority||E.autoPolicy(E.metrics(state.board)).mode==='survive'){continuations=[];return null;}
    for(const item of continuations){
      const s=item.state;
      if(s.piece!==state.piece||(s.hold||null)!==(state.hold||null)||s.profile!==state.profile||
        !!s.allowHold!==!!state.allowHold||(s.canHold!==false)!==(state.canHold!==false)||
        !!s.simpleOnly!==!!state.simpleOnly||!!s.tucks!==!!state.tucks||JSON.stringify(s.board)!==JSON.stringify(state.board)||
        (s.rotationSystem||'srs')!==(state.rotationSystem||'srs')||!!s.allow180!==!!state.allow180||
        (s.chain?.combo||0)!==(state.chain?.combo||0)||(s.chain?.b2b||0)!==(state.chain?.b2b||0)||
        s.queue.some((t,i)=>t!==state.queue[i]))continue;
      // Newly revealed preview tails cannot invalidate a proved path that only
      // used its known prefix. Still reroute from the actually observed pose.
      const result=rebase({candidates:[item.candidate],total:1,before:E.metrics(state.board)},state);
      if(result)return result;
    }
    return null;
  }
  function dispatch(){if(busy||!pending||!background)return;busy={...pending,cancel:new Int32Array(new SharedArrayBuffer(4))};pending=null;background.postMessage(busy);
    watchdog=setTimeout(()=>restart(background,'Search worker timed out'),3000);}
  function deepen(state,key){
    if(busy?.key===key&&!Atomics.load(busy.cancel,0)){pending=null;return;}
    pending={state,key};dispatch();
  }
  function onResult(m){
    if(m.partial){
      if(latest?.key===m.key){const result=rebase(m.result,latest.state);if(result)emit({id:latest.id,stage:'refined',result,ms:m.ms});}
      return;
    }
    clearTimeout(watchdog);const completed=busy;busy=null;
    if(m.aborted){dispatch();return;}
    if(m.result)store(m.key,m.result,m.continuation,completed.state);
    if(m.continuation&&latest?.key===m.key)remember(m.continuation);
    if(latest?.key===m.key){
      const result=continuation(latest.state)||(m.result&&rebase(m.result,latest.state));
      if(!result&&m.result?.candidates.length&&JSON.stringify(completed.state.start)!==JSON.stringify(latest.state.start)){
        cache.delete(m.key);proofs.delete(m.key);contexts.delete(m.key);
        pending={state:latest.state,key:latest.key};
      }else emit(result?{id:latest.id,stage:'final',result,cache:false,ms:m.ms}:{id:latest.id,stage:'done',detail:m.error});
    }
    // One predicted position, only when no real position is waiting.
    if(!pending&&completed&&latest?.key===m.key&&m.result?.candidates.length){
      const c=m.result.candidates[0],q=c.nextQueue;
      if(q.length){const state={...completed.state,board:c.board,piece:q[0],queue:q.slice(1),hold:c.newHold,canHold:true,start:{...E.spawn(q[0]),y:-2},chain:{combo:c.chain.combo,b2b:c.chain.b2b}};
        const key=family(state);if(!cache.has(key))pending={state,key};}
    }
    dispatch();
  }
  function restart(worker,detail){
    if(closing||worker!==background)return;
    background=null;clearTimeout(watchdog);busy=null;
    pending=latest?{state:latest.state,key:latest.key}:null;
    worker.terminate();
    if(latest)emit({id:latest.id,stage:'worker-restart',detail});
    restartTimer=setTimeout(startWorker,100);
  }
  function startWorker(){
    if(closing)return;
    const worker=new Worker(__filename);background=worker;
    worker.on('message',m=>{if(worker===background)onResult(m);});
    worker.on('error',error=>restart(worker,String(error)));
    worker.on('exit',code=>restart(worker,'Search worker exited: '+code));
    dispatch();
  }
  startWorker();
  readline.createInterface({input:process.stdin}).on('line',line=>{
    let m;
    try{
      m=JSON.parse(line);const at=performance.now(),state={...m.state,allowHold:!!m.state.allowHold},key=family(state);
      if(busy&&busy.key!==key)Atomics.store(busy.cancel,0,1);
      latest={id:m.id,at,state,key};
      const planned=continuation(state);
      if(planned){pending=null;emit({id:m.id,stage:'final',cache:true,continuation:true,result:planned,ms:performance.now()-at});return;}
      let hitKey=key;
      if(!cache.has(key)){
        const id=identity(state);
        for(const [k,c] of contexts)if(c.identity===id&&c.queue.length<state.queue.length&&c.queue.every((t,i)=>state.queue[i]===t)){hitKey=k;break;}
      }
      const hit=cache.get(hitKey),cached=hit&&rebase(hit,state);
      if(cached){
        if(proofs.has(hitKey))remember(proofs.get(hitKey));
        const complete=hitKey===key&&!cached.rebasedLost||!!continuation(state)||m.refine===false;
        emit({id:m.id,stage:complete?'final':'refined',cache:true,result:cached,ms:performance.now()-at});
        if(complete)pending=null;else deepen(state,key);
        return;
      }
      // An unreachable cached top-three is not an answer for this pose.
      if(hit){cache.delete(hitKey);proofs.delete(hitKey);contexts.delete(hitKey);}
      const rescue=state.profile==='versus'&&E.autoPolicy(E.metrics(state.board)).mode==='survive';
      // Emergency execution must see NEXT before committing, not wait for a
      // later depth-six answer that usually arrives after the piece is placed.
      const quick=E.analyze({...state,depth:rescue?2:1,...(rescue?{rootLimit:6,beamWidth:2,futureTucks:false}:{})});
      emit({id:m.id,stage:'fast',result:quick,cache:false,ms:performance.now()-at});
      if(state.queue.length&&m.refine!==false)deepen(state,key);
      else emit({id:m.id,stage:'done'});
    }catch(error){emit({id:m?.id,stage:'error',error:String(error)});}
  }).on('close',()=>{closing=true;clearTimeout(restartTimer);clearTimeout(watchdog);background?.terminate();});
}
