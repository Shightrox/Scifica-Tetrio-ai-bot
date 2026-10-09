/* Offline replay of recorded search/route snapshots. Never sends keys. */
const fs=require('node:fs'),E=require('../engine.js');
function verify(advice){
 const s=advice.state,c=advice.candidate;
 if(!s||!c)return;
 const piece=c.piece;
 let pos=c.useHold?E.entry(piece,!!s.simpleOnly):s.start;
 if(!E.fits(s.board,piece,pos))throw Error('initial pose collides');
 for(const [i,action] of c.path.entries()){
  pos=E.move(s.board,piece,pos,action,s.rotationSystem);
  if(!pos)throw Error('unreachable action '+i+': '+action);
  if(c.route?.[i]&&JSON.stringify(pos)!==JSON.stringify(c.route[i].pos))throw Error('checkpoint differs at '+i);
 }
 const points=p=>E.SHAPES[piece][p.r].map(([x,y])=>[x+p.x,y+p.y].join(',')).sort().join(';');
 if(points(pos)!==points(c.pos))throw Error('landing differs');
 const lock=E.lock(s.board,piece,pos);
 if(!lock||JSON.stringify(lock.board)!==JSON.stringify(c.board)||lock.lines!==c.lines)throw Error('lock result differs');
}
function replay(text){
 const seen=new Set(),report={events:0,versions:[],routes:0,failures:[],reasons:{}};
 for(const [index,line] of text.split(/\r?\n/).entries()){
  const start=line.indexOf('{');if(start<0)continue;
  let event;try{event=JSON.parse(line.slice(start));}catch{continue;}
  if(event.schema!==2)continue;
  report.events++;if(!report.versions.includes(event.version))report.versions.push(event.version);
  if(event.reason)report.reasons[event.reason]=(report.reasons[event.reason]||0)+1;
  const a=event.advice;if(!a)continue;
  const key=JSON.stringify([a.state,a.candidate.path,a.candidate.pos]);if(seen.has(key))continue;seen.add(key);
  report.routes++;
  try{verify(a);}catch(error){report.failures.push({line:index+1,reason:String(error)});}
 }
 return report;
}
module.exports={verify,replay};
if(require.main===module){
 if(!process.argv[2]){console.error('Usage: node scripts/replay_trace.cjs path/to/autoplay-events.log');process.exitCode=2;}
 else{const result=replay(fs.readFileSync(process.argv[2],'utf8'));console.log(JSON.stringify(result,null,2));if(result.failures.length)process.exitCode=1;}
}
