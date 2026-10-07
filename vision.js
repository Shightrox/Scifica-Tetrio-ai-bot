(function(root){
 'use strict';
 function classify(r,g,b){const hi=Math.max(r,g,b),lo=Math.min(r,g,b),d=hi-lo;if(hi<78||d<35||d/hi<.28)return null;let h=hi===r?((g-b)/d)%6:hi===g?(b-r)/d+2:(r-g)/d+4;h=(h*60+360)%360;if(h<13||h>=345)return 'Z';if(h<40)return 'L';if(h<65)return 'O';if(h<145)return 'S';if(h<195)return 'I';if(h<258)return 'J';if(h<330)return 'T';return 'Z';}
 function detect(image){const {width:w,height:h,data:d}=image,groups=[];let group=null;
  for(let x=0;x<w;x++){let count=0,first=-1,last=0;for(let y=Math.floor(h*.05);y<h*.96;y+=2){const p=(y*w+x)*4,r=d[p],g=d[p+1],b=d[p+2];if(Math.min(r,g,b)>185&&Math.max(r,g,b)-Math.min(r,g,b)<45){count++;if(first<0)first=y;last=y;}}
   if(count*2>h*.35){if(!group||x>group.x2+2){group={x1:x,x2:x,first,last,count:count*2};groups.push(group);}else{group.x2=x;if(count*2>group.count)Object.assign(group,{first,last,count:count*2});}}
  }
  let best=null;for(let i=0;i<groups.length;i++)for(let j=i+1;j<groups.length;j++){const a=groups[i],b=groups[j],width=b.x1-a.x2-1,y=Math.min(a.first,b.first),height=Math.max(a.last,b.last)-y;if(width<w*.09||width>w*.6)continue;const err=Math.abs(width*2-height)/height+Math.abs(a.first-b.first)/h+Math.abs(a.last-b.last)/h;if(err<.13&&(!best||err<best.error))best={x:a.x2+1,y,w:width,h:width*2,error:err};}return best;
 }
 function sample(image,x,y){x=Math.max(0,Math.min(image.width-1,Math.round(x)));y=Math.max(0,Math.min(image.height-1,Math.round(y)));const p=(y*image.width+x)*4;return classify(image.data[p],image.data[p+1],image.data[p+2]);}
 function read(image,rect){const cw=rect.w/10,ch=rect.h/20,board=Tetris.empty();let ambiguous=0,occupied=0;
  for(let y=0;y<20;y++)for(let x=0;x<10;x++){const count={};for(const oy of [-.16,0,.16])for(const ox of [-.16,0,.16]){const t=sample(image,rect.x+(x+.5+ox)*cw,rect.y+(y+.5+oy)*ch);if(t)count[t]=(count[t]||0)+1;}const sorted=Object.entries(count).sort((a,b)=>b[1]-a[1]);if(sorted[0]?.[1]>=5){board[y][x]=sorted[0][0];occupied++;}else if(sorted.length)ambiguous++;}
  const seen=new Set(),components=[];for(let y=0;y<20;y++)for(let x=0;x<10;x++){if(!board[y][x]||seen.has(`${x},${y}`))continue;const t=board[y][x],q=[[x,y]];seen.add(`${x},${y}`);for(let i=0;i<q.length;i++){const [a,b]=q[i];for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1]]){const xx=a+dx,yy=b+dy,k=`${xx},${yy}`;if(xx>=0&&xx<10&&yy>=0&&yy<20&&board[yy][xx]===t&&!seen.has(k)){seen.add(k);q.push([xx,yy]);}}}components.push({t,cells:q,top:Math.min(...q.map(c=>c[1]))});}
  components.sort((a,b)=>a.top-b.top);let active=null;
  const c=components[0];if(c&&c.cells.length===4&&c.top<16&&(!components[1]||components[1].top>c.top+2)){
   const minx=Math.min(...c.cells.map(p=>p[0])),miny=c.top,normalized=c.cells.map(([x,y])=>`${x-minx},${y-miny}`).sort().join(';');for(let r=0;r<4;r++){const s=Tetris.SHAPES[c.t][r],sx=Math.min(...s.map(p=>p[0])),sy=Math.min(...s.map(p=>p[1]));if(s.map(([x,y])=>`${x-sx},${y-sy}`).sort().join(';')===normalized){active={piece:c.t,start:{x:minx-sx,y:miny-sy,r}};break;}}
   if(active)for(const [x,y] of c.cells)board[y][x]=null;
  }
  function regionCounts(x1,x2,y1,y2){const counts={};for(let y=Math.max(0,y1);y<Math.min(image.height,y2);y+=3)for(let x=Math.max(0,x1);x<Math.min(image.width,x2);x+=3){const t=sample(image,x,y);if(t)counts[t]=(counts[t]||0)+1;}return Object.entries(counts).sort((a,b)=>b[1]-a[1]);}
  const queue=[];let last=null,blank=0;for(let y=rect.y+ch*.6;y<Math.min(image.height,rect.y+ch*15.7);y+=3){const a=regionCounts(rect.x+rect.w+cw*.9,rect.x+rect.w+cw*5.1,y,y+1),t=a[0]?.[1]>cw*.09?a[0][0]:null;if(!t){blank++;continue;}if(t!==last||blank>3){queue.push(t);last=t;}blank=0;}
  const hc=regionCounts(rect.x-cw*4.8,rect.x-cw*.3,rect.y+ch*.9,rect.y+ch*3.6);const hold=hc[0]?.[1]>20?hc[0][0]:null;
  return {board,active,queue:queue.slice(0,5),hold,ambiguous,occupied};
 }
 root.Vision={classify,detect,read};if(typeof module!=='undefined')module.exports=root.Vision;
})(typeof self!=='undefined'?self:globalThis);
