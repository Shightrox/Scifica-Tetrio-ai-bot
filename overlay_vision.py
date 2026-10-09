"""Small, vectorized screen reader. Pixels stay in this process."""
import numpy as np
import time
from field_geometry import colored_boards
from notice_vision import notice_mask
from block_vision import SpawnEdges, colour_support

TYPES = ('', 'I', 'O', 'T', 'S', 'Z', 'J', 'L', 'G')
BASE = {'T':[(1,0),(0,1),(1,1),(2,1)], 'I':[(0,1),(1,1),(2,1),(3,1)],
        'O':[(0,0),(1,0),(0,1),(1,1)], 'S':[(1,0),(2,0),(0,1),(1,1)],
        'Z':[(0,0),(1,0),(1,1),(2,1)], 'J':[(0,0),(0,1),(1,1),(2,1)],
        'L':[(2,0),(0,1),(1,1),(2,1)]}
SHAPES = {}
for name, base in BASE.items():
    rotations = []
    for rotation in range(4):
        p = base[:]
        for _ in range(rotation if name != 'O' else 0):
            n = 3 if name == 'I' else 2
            p = [(n-y, x) for x,y in p]
        rotations.append(p)
    SHAPES[name] = rotations

def classes(rgb, gray=False):
    f = rgb.astype(np.float32)
    hi, lo = f.max(axis=-1), f.min(axis=-1)
    d = hi-lo
    safe = np.maximum(d, 1)
    r,g,b = f[...,0], f[...,1], f[...,2]
    h = np.where(hi == r, (g-b)/safe, np.where(hi == g, (b-r)/safe+2, (r-g)/safe+4))
    h = (h*60+360)%360
    out = np.select([h<13,h<40,h<65,h<145,h<195,h<258,h<330,h<345], [5,7,2,4,1,6,3,5], default=5).astype(np.uint8)
    out[(hi<78)|(d<35)|(d/np.maximum(hi,1)<.28)] = 0
    if gray:out[(lo>=65)&(d<26)]=8
    return out

def grid_votes(samples, valid):
    """The spawn area has no dark board backing: don't classify scenery as cells.

    Standard blocks have saturated, coherent centres. Above the grid, require
    that evidence and exclude neutral pixels (sky is not garbage). Inside the
    board retain the more permissive palette and gray-garbage recognition.
    """
    votes=classes(samples,gray=True)
    top=samples[:4].astype(np.int16)
    hi=top.max(3);lo=top.min(3);chroma=hi-lo
    vivid=(hi>=110)&(chroma>=65)&(chroma/np.maximum(hi,1)>=.4)
    # Keep the majority colour cluster, so embossed borders / highlights do not
    # reject the entire block when calibration shifts by a couple of pixels.
    distance=np.abs(top[:,:,:,None,:]-top[:,:,None,:,:]).max(4)
    coherent=(distance<=35).sum(3)>=5
    votes[:4]=np.where(vivid&coherent&(votes[:4]!=8),votes[:4],0)
    return np.where(valid,votes,0)

def detect_neutral(rgb):
    """Find two long neutral borders with a 1:2 board aspect ratio."""
    h,w = rgb.shape[:2]
    step = max(1,h//900)
    arr = rgb[::step]
    white = (arr.min(2)>185)&((arr.max(2).astype(int)-arr.min(2))<45)
    counts = white.sum(0)*step
    xs = np.flatnonzero(counts>h*.27)
    groups=[]
    for x in xs:
        if not groups or x>groups[-1][-1]+2: groups.append([])
        groups[-1].append(int(x))
    borders=[]
    for g in groups:
        x=max(g,key=lambda x:counts[x]); ys=np.flatnonzero(white[:,x])*step
        borders.append((g[0],g[-1],int(ys[0]),int(ys[-1])))
    best=None
    for i,a in enumerate(borders):
        for b in borders[i+1:]:
            width=b[0]-a[1]-1; height=max(a[3],b[3])-min(a[2],b[2])
            if width<60 or not height: continue
            error=abs(width*2-height)/height+abs(a[2]-b[2])/h+abs(a[3]-b[3])/h
            if error<.13 and (best is None or error<best[0]): best=(error,(a[1]+1,min(a[2],b[2]),width,width*2))
    return best[1] if best else None

def detect_candidates(rgb):
    stride=max(1,int(np.ceil(np.sqrt(rgb.shape[0]*rgb.shape[1]/550000))))
    candidates=[(score*stride,tuple(v*stride for v in region)) for score,region in colored_boards(rgb[::stride,::stride])]
    neutral=detect_neutral(rgb)
    if neutral:candidates.append((neutral[2],neutral))
    return [region for score,region in sorted(candidates,key=lambda c:c[0],reverse=True)]


def board_evidence(rgb,region):
    """A rectangular border alone cannot authorize automatic recalibration."""
    x,y,w,h=region;ih,iw=rgb.shape[:2]
    if x<0 or y<0 or w<60 or x+w>iw or y+h>ih+3:return False
    top=min(y,round(h/5));left=min(x,round(w*.75))
    crop=rgb[y-top:min(ih,y+h),x-left:min(iw,x+round(w*1.6))]
    v=Reader().read(crop,w,h,top=top,left=left)
    # Preview silhouettes are independent evidence at the proposed cell size.
    # An OUT OF FOCUS notice can obscure the board, but not its previews/spawn.
    return bool(v['active'] and v['ambiguous']==0 and len(v['queue'])>=2)


def detect(rgb,verified=False,preferred=None):
    candidates=detect_candidates(rgb)
    if preferred:
        # Prefer the previously selected board over opponent boards / scenery.
        px,py,pw,ph=preferred
        candidates.sort(key=lambda r:abs(r[0]-px)+abs(r[1]-py)+2*abs(r[2]-pw))
    for region in candidates:
        if not verified or board_evidence(rgb,region):return region
    return None

def preview_pieces(rgb,cell):
    """Read actual four-cell preview shapes, excluding frame bars and headings."""
    if not rgb.size:return []
    stride=max(1,round(cell/15));ids=classes(rgb[::stride,::stride]);unit=cell/stride
    # Tall uniform colored strips belong to panel frames / scenery.
    for ident in range(1,8):ids[:,(ids==ident).mean(0)>.80]=0
    totals=np.stack([(ids==i).sum(1) for i in range(1,8)],axis=1)
    rows=np.where(totals.max(1)>unit*.35,totals.argmax(1)+1,0)
    groups=[];last=0;blank=0
    for y,t in enumerate(rows):
        if not t:blank+=1;continue
        if t!=last or blank>max(1,unit*.18):groups.append([int(t),y,y])
        else:groups[-1][2]=y
        last=t;blank=0
    result=[]
    for ident,y1,y2 in groups:
        ys,xs=np.nonzero(ids[y1:y2+1]==ident)
        if not len(xs):continue
        columns=np.unique(xs)
        parts=np.split(columns,np.flatnonzero(np.diff(columns)>max(2,unit*.22))+1)
        part=max(parts,key=lambda p:int((ids[y1:y2+1,p]==ident).sum()))
        x1,x2=int(part[0]),int(part[-1])
        yy,_=np.nonzero(ids[y1:y2+1,x1:x2+1]==ident)
        y2=y1+int(yy.max());y1+=int(yy.min())
        bw=x2-x1+1;bh=y2-y1+1
        cols,rows_count=round(bw/unit),round(bh/unit)
        name=TYPES[ident];shape=BASE[name];sx=min(x for x,y in shape);sy=min(y for x,y in shape)
        wanted={(x-sx,y-sy) for x,y in shape}
        if cols!=max(x for x,y in wanted)+1 or rows_count!=max(y for x,y in wanted)+1:continue
        if abs(bw/unit-cols)>.35 or abs(bh/unit-rows_count)>.35:continue
        actual=set()
        for cy in range(rows_count):
            for cx in range(cols):
                px=min(ids.shape[1]-1,int(x1+(cx+.5)*bw/cols));py=min(ids.shape[0]-1,int(y1+(cy+.5)*bh/rows_count))
                if ids[py,px]==ident:actual.add((cx,cy))
        if actual==wanted:result.append(name)
    return result

def game_overlay(rgb,width,height,top):
    """Recognize the red rectangular focus notice as an occlusion, not blocks."""
    area=rgb[top:top+height,:width:2][::2]
    if not area.size:return None
    r,g,b=area[:,:,0],area[:,:,1],area[:,:,2]
    red=(r>180)&(g<45)&(b<45)
    ys=np.flatnonzero(red.sum(1)>red.shape[1]*.65)
    if len(ys)<2:return None
    first,last=int(ys[0]),int(ys[-1])
    if not height*.035<=(last-first)<=height*.23:return None
    xs=np.flatnonzero(red[first:last+1].mean(0)>.85)
    if len(xs)>=2 and xs[-1]-xs[0]>red.shape[1]*.65:return 'focus-notice'
    return None

def fit_active(points, type_id):
    if len(points)!=4 or not type_id: return None
    name=TYPES[int(type_id)]
    if name not in SHAPES:return None
    mx=min(x for x,y in points); my=min(y for x,y in points)
    key=sorted((x-mx,y-my) for x,y in points)
    for r,shape in enumerate(SHAPES[name]):
        sx=min(x for x,y in shape); sy=min(y for x,y in shape)
        if sorted((x-sx,y-sy) for x,y in shape)==key:
            return {'piece':name,'start':{'x':mx-sx,'y':my-sy,'r':r}}
    return None

def fit_partial(extended, settled, name):
    """Recover a unique pose of a known piece from >=3 observed cells.

    Exclude the trusted stack and reject ties; a guessed rotation is not a pose.
    One unrelated cell above the grid is allowed (animated background).
    """
    ident=TYPES.index(name)
    ys,xs=np.nonzero((extended==ident)&(settled==0))
    seen={(int(x),int(y)-4) for x,y in zip(xs,ys)}
    if not 3<=len(seen)<=5:return None
    options={}
    for r,shape in enumerate(SHAPES[name]):
        for sx,sy in seen:
            for dx,dy in shape:
                x,y=sx-dx,sy-dy
                points=frozenset((x+xx,y+yy) for xx,yy in shape)
                if any(not (0<=xx<10 and -4<=yy<20) or settled[yy+4,xx] for xx,yy in points):continue
                matched=len(points&seen);extra=seen-points
                if matched<3 or len(extra)>1 or any(yy>=0 for xx,yy in extra):continue
                # Missing pixels may be dark/unknown, but not another piece colour.
                if any(extended[yy+4,xx] not in (0,ident) for xx,yy in points):continue
                options.setdefault(points,({'piece':name,'start':{'x':x,'y':y,'r':r}},matched))
    if not options:return None
    best=max(v[1] for v in options.values());winners=[(p,v[0]) for p,v in options.items() if v[1]==best]
    return (winners[0][1],list(winners[0][0])) if len(winners)==1 else None


def fit_fragments(support, settled, masked, name, weak=None):
    """Recover only a unique pose from fresh broad areas of >=2 visible cells.

    Missing cells must actually be inside the notice. Neither a previous pose
    nor a sent key is evidence that a currently hidden cell moved or rotated.
    """
    ys,xs=np.nonzero(support&(settled==0))
    seen=frozenset((int(x),int(y)-4) for x,y in zip(xs,ys))
    if not 2<=len(seen)<=4:return None
    if weak is not None:
        ys,xs=np.nonzero(weak&(settled==0))
        seen=seen|frozenset((int(x),int(y)-4) for x,y in zip(xs,ys))
        if len(seen)>4:return None
    options={}
    for r,shape in enumerate(SHAPES[name]):
        for sx,sy in seen:
            for dx,dy in shape:
                x,y=sx-dx,sy-dy
                points=frozenset((x+xx,y+yy) for xx,yy in shape)
                if not seen<=points:continue
                if any(not (0<=xx<10 and -4<=yy<20) or settled[yy+4,xx] for xx,yy in points):continue
                if any(yy<0 or not masked[yy,xx] for xx,yy in points-seen):continue
                options.setdefault(points,{'piece':name,'start':{'x':x,'y':y,'r':r}})
    if len(options)!=1:return None
    points,candidate=next(iter(options.items()))
    return candidate,list(points)

class Reader:
    def __init__(self):
        self.locked=None
        self.samples=None
        self.size=None
        self.queue=[]
        self.last_active=None
        self.generation=0
        self.pending_spawn=None
        self.pending_age=0
        self.inferred_frames=0
        self.hold=None;self.hold_known=False;self.hold_sample=None;self.hold_count=0
        self.unstable_board=None;self.unstable_count=0
        self.inferred_at=None;self.partial_pose=None;self.partial_count=0
        self.colour_templates={}
        self.round_id=0;self.blocked_at=None
        self.accepted_queue=[];self.round_probe=None

    def probe_round(self,extended,queue,blocked,notice):
        """Recognize a new empty round before restoring old cells under masks.

        Compare with the last *accepted* preview: countdown animation may have
        already replaced the raw NEXT samples long before spawn is visible.
        """
        previous=self.accepted_queue
        overlap=min(len(previous),len(queue));shift=min(3,len(previous)-1,len(queue))
        changed=overlap>=2 and previous[:overlap]!=queue[:overlap]
        advanced=shift>=2 and queue[:shift]==previous[1:shift+1]
        evidence=self.hold_known and self.hold is None or self.blocked_at is not None and time.perf_counter()-self.blocked_at<3
        if self.locked is None or blocked or notice or not evidence or not changed or advanced or len(queue)<3:
            self.round_probe=None;return None
        for ident,name in enumerate(TYPES[1:8],1):
            # The first usable frame may arrive after gravity has moved spawn
            # well into the empty grid. Require its column/orientation, not y.
            ys,xs=np.nonzero(extended==ident)
            points=[(int(x),int(y)-4) for x,y in zip(xs,ys)]
            candidate=fit_active(points,ident)
            if not candidate:continue
            pos=candidate['start']
            if pos['r']!=0 or pos['x']!=(4 if name=='O' else 3) or not -3<=pos['y']<20:continue
            remaining=extended[4:].copy()
            for x,y in points:
                if y>=0:remaining[y,x]=0
            if remaining.any():continue
            signature=(name,pos['x'],tuple(queue))
            old=self.round_probe
            count=old[1]+1 if old and old[0]==signature else 1
            self.round_probe=(signature,count)
            if count>=3:return candidate
            return None
        self.round_probe=None;return None

    def legal_lock(self, observed):
        """Verify a lock/line clear against the last known settled stack.

        Queue movement alone is not enough: HOLD also moves NEXT.
        """
        if self.locked is None or not self.last_active:return False
        name=self.last_active['piece'];ident=TYPES.index(name)
        old=self.locked
        def fits(shape,x,y):
            return all(0<=x+dx<10 and -4<=y+dy<20 and (y+dy<0 or old[y+dy,x+dx]==0) for dx,dy in shape)
        # First try the exact visible position (also handles tucks), then
        # straight drops for a hard drop that happened between captured frames.
        options=[(SHAPES[name][self.last_active['start']['r']],self.last_active['start']['x'],self.last_active['start']['y'])]
        options += [(shape,x,-3) for shape in SHAPES[name] for x in range(-3,10)]
        for shape,x,y in options:
            if not fits(shape,x,y):continue
            while fits(shape,x,y+1):y+=1
            if any(y+dy<0 for dx,dy in shape):continue
            b=old.copy()
            for dx,dy in shape:b[y+dy,x+dx]=ident
            kept=b[~np.all(b>0,axis=1)]
            cleared=np.vstack([np.zeros((20-len(kept),10),np.uint8),kept])
            if np.array_equal(cleared,observed):return True
            for n in range(1,13):
                bottom=observed[-n:]
                if not np.all(((bottom==8).sum(1)>=8)&((bottom>0).sum(1)<10)):break
                if np.array_equal(cleared[n:],observed[:-n]):return True
        return False

    def read(self, rgb, board_width, board_height, top=0, left=0, action=None):
        cell=board_width/10
        if left>=cell*4.8:
            crop=rgb[max(0,round(top+cell*.65)):round(top+cell*4.2),max(0,round(left-cell*6.6)):round(left-cell*.55)]
            if crop.size:
                pieces=preview_pieces(np.clip(crop.astype(np.float32)*1.5,0,255).astype(np.uint8),cell)
                sample=pieces[0] if len(pieces)==1 else None
                # Inspect the slot interior for emptiness, not its white header
                # and border. Grey disabled pieces remain unknown to vision.
                interior=rgb[round(top+cell*1.1):round(top+cell*3.6),
                             max(0,round(left-cell*4.6)):round(left-cell*1.4)]
                empty=interior.size and (interior.max(2)<32).mean()>.985
                known=sample is not None or not pieces and empty
                if known:
                    if sample==self.hold_sample:self.hold_count+=1
                    else:self.hold_sample=sample;self.hold_count=1;self.hold_known=False
                    if self.hold_count>=2:self.hold=sample;self.hold_known=True
                else:self.hold_known=False;self.hold_count=0
        rgb=rgb[:,left:]
        h,w=rgb.shape[:2]
        blocked=game_overlay(rgb,board_width,board_height,top)
        if blocked:self.blocked_at=time.perf_counter()
        size=(board_width,board_height,w,h,top)
        if size!=self.size:
            self.size=size
            offsets=[(dx,dy) for dy in (-.16,0,.16) for dx in (-.16,0,.16)]
            xx=np.array([[(x+.5+dx)*board_width/10 for dx,dy in offsets] for x in range(10)]).round().astype(int)
            yy=np.array([[top+(y+.5+dy)*board_height/20 for dx,dy in offsets] for y in range(-4,20)]).round().astype(int)
            self.samples=(np.clip(yy[:,None,:],0,h-1),np.clip(xx[None,:,:],0,w-1))
            self.valid=(yy[:,None,:]>=0)&(yy[:,None,:]<h)
            self.spawn_edges=SpawnEdges(board_width,board_height,top,rgb.shape)
            offsets=[(dx,dy) for dy in np.linspace(-.36,.36,7) for dx in np.linspace(-.36,.36,7)]
            xx=np.array([[(x+.5+dx)*board_width/10 for dx,dy in offsets] for x in range(10)]).round().astype(int)
            yy=np.array([[top+(y+.5+dy)*board_height/20 for dx,dy in offsets] for y in range(-4,20)]).round().astype(int)
            self.notice_samples=(np.clip(yy[:,None,:],0,h-1),np.clip(xx[None,:,:],0,w-1))
        samples=rgb[self.samples]
        votes=grid_votes(samples,self.valid)
        counts=np.stack([(votes==i).sum(2) for i in range(9)],axis=2)
        extended=counts.argmax(2).astype(np.uint8)
        extended[counts.max(2)<5]=0
        if top:
            extended=self.spawn_edges.filter(rgb,extended,np.median(samples,axis=2),SHAPES,TYPES)
        board=extended[4:].copy()
        masked=np.zeros((20,10),bool)
        if self.locked is not None and not blocked:
            patches=rgb[self.notice_samples]
            patch_ids=classes(patches,gray=True)
            masked=notice_mask(patches[4:],patch_ids[4:])
            for y in np.flatnonzero(masked.any(1)):
                if (board[y]==8).sum()>=7 and (self.locked[y]==8).sum()<7:masked[y]=True
        notice=bool(masked.any());forecast=None
        if notice and action and action.get('action')=='DROP' and 0<=time.perf_counter()-action['at']<1.5:
            before=action.get('before_board')
            if before is not None and [[TYPES[int(v)] or None for v in row] for row in self.locked]==before:
                forecast=np.array([[TYPES.index(v) if v else 0 for v in row] for row in action['board']],np.uint8)
        garbage_rise=0
        if self.locked is not None:
            for n in range(1,13):
                bottom=board[-n:]
                if not np.all(((bottom==8).sum(1)>=8)&((bottom>0).sum(1)<10)):break
                shifted=np.vstack([self.locked[n:],bottom])
                visible=~masked
                extra=int(((board>0)&(shifted==0)&visible).sum())
                occupied=(shifted>0)&visible
                rise_seen=np.any((shifted>0)&(self.locked==0)&visible)
                if extra<=4 and rise_seen and np.all(board[occupied]==shifted[occupied]):
                    self.locked=shifted;garbage_rise=n;self.generation+=1
                    if forecast is not None:forecast=np.vstack([forecast[n:],bottom])
                    break
        ambiguous=int(((counts[4:].max(2)<5)&(votes[4:].max(2)>0)&~masked).sum())
        cell=board_width/10
        x1=int(board_width+cell*.55);x2=min(w,int(board_width+cell*5.5))
        y1=max(0,round(top+cell*.6));y2=min(h,round(top+cell*16))
        queue=preview_pieces(rgb[y1:y2,x1:x2],cell) if x2>x1 and y2>y1 else []
        queue=queue[:5]
        fresh=self.probe_round(extended,queue,blocked,notice)
        if self.round_probe and not fresh:
            return {'board':[[TYPES[int(v)] or None for v in row] for row in self.locked],'active':None,'queue':queue,'ambiguous':1,
                    'event':'round-probe','source':'pixels','generation':self.generation,'roundId':self.round_id,
                    'garbage_rise':0,'hold':self.hold,'holdKnown':self.hold_known,'spawnAgeMs':None,'blocked':None,'noticeCells':0}
        if fresh:
            self.round_id+=1;self.generation+=1
            self.locked=np.zeros((20,10),np.uint8);self.last_active=fresh
            self.queue=queue[:];self.accepted_queue=queue[:];self.pending_spawn=None;self.pending_age=0
            self.inferred_at=None;self.partial_pose=None;self.partial_count=0;self.inferred_frames=0
            self.unstable_count=0;self.unstable_board=None;self.round_probe=None;self.blocked_at=None
            return {'board':[[None]*10 for _ in range(20)],'active':fresh,'queue':queue,'ambiguous':0,
                    'event':'round-reset','source':'pixels','generation':self.generation,'roundId':self.round_id,
                    'garbage_rise':0,'hold':self.hold,'holdKnown':self.hold_known,'spawnAgeMs':None,'blocked':None,'noticeCells':0}
        old_queue=self.queue[:]
        count=min(3,len(old_queue)-1,len(queue))
        advanced=count>=2 and queue!=old_queue and queue[:count]==old_queue[1:count+1]
        predicted_notice=notice and forecast is not None and advanced and action.get('queue')==old_queue
        raw_extended=extended.copy() if notice else None
        if notice:
            model=forecast if predicted_notice else self.locked
            extended[4:][masked]=model[masked];board=extended[4:].copy()
        if advanced:self.pending_spawn=old_queue[0];self.pending_age=0
        if self.pending_spawn:
            self.pending_age+=1
            if self.pending_age>30:self.pending_spawn=None
        expected=self.pending_spawn
        active=None; active_points=[]
        settled=np.vstack([np.zeros((4,10),np.uint8),self.locked]) if self.locked is not None else None
        if settled is not None and np.all(extended[settled>0]==settled[settled>0]):
            # Ignore unrelated background colours above the board by trying
            # the expected/previous piece colour independently.
            preferences=[expected] if expected else ([self.last_active['piece']] if self.last_active else list(BASE))
            for name in preferences:
                if not name:continue
                ys,xs=np.nonzero((extended==TYPES.index(name))&(settled==0))
                points=[(int(x),int(y)-4) for x,y in zip(xs,ys)]
                candidate=fit_active(points,TYPES.index(name))
                if candidate and (not advanced or min(y for x,y in points)<4):
                    active=candidate;active_points=points;break
        if not active:
            visited=set(); components=[]
            for y,x in zip(*np.nonzero(extended)):
                if (x,y) in visited: continue
                ident=extended[y,x]; q=[(int(x),int(y))]; visited.add((x,y))
                for xx,yy in q:
                    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        nx,ny=xx+dx,yy+dy
                        if 0<=nx<10 and 0<=ny<24 and (nx,ny) not in visited and extended[ny,nx]==ident:
                            visited.add((nx,ny));q.append((nx,ny))
                points=[(x,y-4) for x,y in q]
                components.append((min(y for x,y in points),ident,points))
            components.sort(key=lambda c:c[0])
            visible_components=[c for c in components if c[0]>=0]
            visible_top=visible_components[0][0] if visible_components else 20
            for yy,ident,points in components:
                # A complete observed spawn outranks a stale NEXT/HOLD hint.
                if yy>=17 or yy>=0 and expected and TYPES[int(ident)]!=expected:continue
                candidate=fit_active(points,ident)
                if not candidate:continue
                if notice and settled is not None and all(y>=0 and settled[y+4,x] for x,y in points):continue
                if yy<0 or yy==visible_top and not advanced:
                    remaining=board.copy()
                    for xx,yy2 in points:
                        if yy2>=0:remaining[yy2,xx]=0
                    other_top=min((c[0] for c in visible_components if c[2]!=points),default=20)
                    if yy<0 or other_top>yy+2 or self.locked is not None and np.array_equal(remaining,self.locked):
                        active=candidate;active_points=points;break
                elif advanced and yy<4:
                    active=candidate;active_points=points;break
        source='pixels';event='tracking'
        if not active and notice:
            name=expected or (action.get('expected') if action and action.get('action')=='HOLD' else None) or (self.last_active['piece'] if self.last_active else None)
            if name:
                support,weak=colour_support(patches,TYPES.index(name),patch_ids,self.colour_templates.get(name),fragments=True)
                # Above-grid scenery still needs the independently checked
                # tetromino contour; text recovery cannot bypass that check.
                support[:4] &= raw_extended[:4]==TYPES.index(name)
                weak[:4] &= raw_extended[:4]==TYPES.index(name)
                hidden_settled=np.vstack([np.zeros((4,10),np.uint8),model])
                fragments=fit_fragments(support,hidden_settled,masked,name,weak=weak)
                if fragments:active,active_points=fragments;source='fragments'
        if not active and settled is not None and np.all(extended[settled>0]>0):
            name=expected or (self.last_active['piece'] if self.last_active else None)
            partial=fit_partial(extended,settled,name) if name else None
            if partial:
                candidate,points=partial
                pose=(candidate['piece'],candidate['start']['x'],candidate['start']['r'])
                if pose==self.partial_pose:self.partial_count+=1
                else:self.partial_pose=pose;self.partial_count=1
                if self.partial_count>=2:active=candidate;active_points=points;source='partial'
            else:self.partial_pose=None;self.partial_count=0
        else:self.partial_pose=None;self.partial_count=0
        spawn_board=board
        if not active and expected:
            # During spawn fade only 1-3 cells may be visible. Remove only the
            # expected colour near spawn, then still prove the preceding lock.
            spawn_board=board.copy()
            ys,xs=np.nonzero(spawn_board[:4]==TYPES.index(expected))
            if 0<len(xs)<=3:
                for yy,xx in zip(ys,xs):spawn_board[yy,xx]=0
        if not active and expected and self.legal_lock(spawn_board):
            # New piece can still be invisible during spawn animation. Use the
            # previous NEXT head only after validating the changed settled board.
            active={'piece':expected,'start':{'x':4 if expected=='O' else 3,'y':-2,'r':0}}
            source='next';event='lock'
            board=spawn_board
            self.inferred_at=time.perf_counter()
        elif not active and self.inferred_at is not None and time.perf_counter()-self.inferred_at<2 and self.locked is not None and queue==self.queue:
            # Preserve the known type through a partly drawn new piece. This
            # does NOT confirm its position or any movement sent by the player.
            mask=self.locked>0;extra=(board>0)&~mask
            ident=TYPES.index(self.last_active['piece'])
            if np.all(board[mask]>0) and int(extra.sum())<=4 and np.all(board[extra]==ident):
                active=self.last_active;source='next';board=self.locked.copy()
        if active:
            for x,y in active_points:
                if y>=0:board[y,x]=0
            if blocked:
                return {'board':None,'active':active,'queue':queue,'ambiguous':ambiguous,
                        'event':'occluded','source':'pixels','generation':self.generation,'roundId':self.round_id,'garbage_rise':0,
                        'hold':self.hold,'holdKnown':self.hold_known,'spawnAgeMs':None,'blocked':blocked}
            if notice:
                same=np.array_equal(board>0,self.locked>0)
                predicted=predicted_notice and active['piece']==old_queue[0] and np.array_equal(board>0,forecast>0)
                held=action and action.get('action')=='HOLD' and active['piece']==action.get('expected')
                legal=self.legal_lock(board) if not same or advanced else False
                # Never learn hidden cells from lettering, or accept a guessed
                # post-drop stack merely because the NEXT preview advanced.
                if not predicted and (not same and not legal or advanced and not legal and not held):
                    active=None;active_points=[];ambiguous=max(1,ambiguous);event='notice-uncertain';board=self.locked.copy()
                elif predicted:
                    board=forecast.copy()
        if active:
            if self.locked is not None and np.array_equal(board>0,self.locked>0):
                # Block colours can brighten during effects; occupancy is stable.
                board=self.locked.copy()
            if self.locked is not None and not np.array_equal(self.locked,board) and not self.legal_lock(board):
                if self.unstable_board is not None and np.array_equal(self.unstable_board,board):self.unstable_count+=1
                else:self.unstable_board=board.copy();self.unstable_count=1
                # Repeated occlusion is not evidence of a legal board change.
                active=None;active_points=[];ambiguous=max(1,ambiguous);event='unstable'
                board=self.locked.copy()
            else:self.unstable_count=0;self.unstable_board=None
        if active:
            if source=='pixels' and active_points and not any(y>=0 and masked[y,x] for x,y in active_points):
                colours=np.array([samples[y+4,x] for x,y in active_points]).reshape(-1,3)
                chosen=colours[classes(colours)==TYPES.index(active['piece'])]
                if len(chosen)>=20:self.colour_templates[active['piece']]=np.median(chosen,axis=0)
            if event!='round-reset' and (advanced or self.locked is not None and not np.array_equal(self.locked,board)):
                self.generation+=1;event='lock' if advanced else 'new-piece'
            self.locked=board.copy()
            self.last_active=active
            if queue:self.accepted_queue=queue[:]
            self.pending_spawn=None
            self.inferred_frames=self.inferred_frames+1 if source=='next' else 0
            if source!='next':self.inferred_at=None
        if advanced and not active:event='transition'
        if garbage_rise:event='garbage'
        if queue:self.queue=queue[:]
        return {'board':[[TYPES[int(v)] or None for v in row] for row in board],
                'active':active,'queue':queue,'ambiguous':ambiguous,'event':event,
                'source':source,'generation':self.generation,'garbage_rise':garbage_rise,
                'roundId':self.round_id,
                'hold':self.hold,'holdKnown':self.hold_known,
                'spawnAgeMs':(time.perf_counter()-self.inferred_at)*1000 if source=='next' and self.inferred_at is not None else None,
                'blocked':blocked,'noticeCells':int(masked.sum())}
