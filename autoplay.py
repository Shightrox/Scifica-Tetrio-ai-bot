"""Closed-loop controller. Pure logic with an injected, guarded key-tap sink."""
from overlay_vision import SHAPES
import random
from preferences import bounded

def cells(piece,pos):
    return sorted((pos['x']+x,pos['y']+y) for x,y in SHAPES[piece][pos['r']])

def fits(board,piece,pos):
    return all(0<=x<10 and -4<=y<20 and (y<0 or not board[y][x]) for x,y in cells(piece,pos))

def landing(board,piece,pos):
    p=dict(pos)
    if not fits(board,piece,p):return None
    while fits(board,piece,dict(p,y=p['y']+1)):p['y']+=1
    return p

def pose_as(piece,points,rotation):
    shape=SHAPES[piece][rotation]
    pos=dict(x=min(x for x,y in points)-min(x for x,y in shape),
             y=min(y for x,y in points)-min(y for x,y in shape),r=rotation)
    return pos if cells(piece,pos)==sorted(points) else None

def fell_from(board,piece,pos,points):
    """Only unobstructed gravity may separate a checkpoint and its pixels."""
    if not pos:return False
    actual=pose_as(piece,points,pos['r'])
    if not actual or actual['x']!=pos['x'] or actual['y']<pos['y']:return False
    return all(fits(board,piece,dict(pos,y=y)) for y in range(pos['y'],actual['y']+1))

def garbage_shift(expected,actual):
    for n in range(1,13):
        if not all(sum(v=='G' for v in r)>=8 and sum(bool(v) for v in r)<10 for r in actual[-n:]):break
        if expected[n:]==actual[:-n]:return n
    return 0

class AutoPlayer:
    def __init__(self,tap,release=lambda:None,rng=None):
        self.tap=tap;self.release=release;self.enabled=False;self.phase='off';self.reason='Autopilot disarmed'
        self.plan=None;self.waiting=None;self.started=0;self.last_seen=0;self.chain={'combo':0,'b2b':0};self.placed=0
        self.planning_key=None;self.planning_at=0
        self.paused_at=None;self.retries=0
        self.hold_blocked=False;self.held_piece=None;self.verified_hold=None;self.hold_verified=False
        self.early_spawn=None
        self.pose=None
        self.recovery=None;self.revision=0;self.failed_motion=None
        self.vk={'L':0x25,'R':0x27,'CW':0x58,'CCW':0x5a,'180':0x41,'SD':0x28,'DROP':0x20,'HOLD':0x10}
        self.rng=rng or random.Random();self.key_rate=30;self.humanization=0;self.dynamic_tempo=0
        self.last_tap_at=float('-inf');self.pace_factor=1;self.human_considered=False
        self.reset_rhythm()

    def configure(self,key_rate=30,humanization=0,dynamic_tempo=0):
        self.key_rate=bounded(key_rate,2,30,30)
        self.humanization=bounded(humanization,0,100,0)
        self.dynamic_tempo=bounded(dynamic_tempo,0,100,0)

    def reset_rhythm(self):
        self.timing_started=None;self.thinking_done=False;self.think_delay=0
        self.tap_delay=0;self.burst_scale=1
        self.deep_replanned=False

    def tempo_safety(self,state,candidate,observed):
        if not observed or self.retries or candidate.get('auto',{}).get('mode')=='survive':return 0
        if any(any(row) for row in state['board'][:11]):return 0
        end=landing(state['board'],state['piece'],state['start'])
        clearance=end['y']-state['start']['y'] if end else 0
        if clearance<=5:return 0
        return .35 if clearance<=9 or state['start']['y']>3 else 1

    def pace_ready(self,now,state,candidate,observed):
        """Non-blocking deadlines, sampled once per placement/tap, never per frame.

        HOLD shares the placement's rhythm. Fresh pixels can shorten a wait as
        the piece falls or danger rises. Acknowledgements run before this gate.
        """
        if candidate.get('inTuck'):return True # finish before lock delay; feedback still runs first
        strength=self.dynamic_tempo/100
        safety=self.tempo_safety(state,candidate,observed) if strength else 0
        if strength and self.timing_started is None:
            self.timing_started=now
            self.burst_scale=self.rng.uniform(.7,1.3)
            self.think_delay=self.rng.uniform(.08,.26)
            if self.rng.random()<.25:self.think_delay+=self.rng.uniform(.08,.20)
        thinking=(strength and not self.thinking_done and
                  now<self.timing_started+self.think_delay*strength*safety)
        if not thinking and self.timing_started is not None:self.thinking_done=True
        interval=0 if self.key_rate>=30 else 1/self.key_rate
        gap=interval*self.pace_factor+self.tap_delay*strength*safety
        if thinking or now-self.last_tap_at<gap:
            self.phase='pacing'
            self.reason='Thinking' if thinking else ('Dynamic tempo' if strength and safety else 'Tempo')
            return False
        return True

    def send(self,action,now):
        if not self.tap(self.vk[action]):return False
        self.last_tap_at=now
        self.pace_factor=1+self.rng.uniform(-.12,.12)*self.humanization/100
        if self.dynamic_tempo:
            self.tap_delay=self.rng.uniform(.025,.10)*self.burst_scale
            if self.rng.random()<.18:self.tap_delay+=self.rng.uniform(.03,.09)
        else:self.tap_delay=0
        return True

    def human_prefix(self,state,candidate,observed):
        """One optional lateral out-and-back pair; both taps use normal feedback.

        No random DROP, HOLD or rotation. No flourish on a crowded board, low
        landing clearance, inferred pose or recovery attempt. A failed pair is
        abandoned and replanned from pixels, never corrected blindly.
        """
        if self.human_considered or not observed:return []
        self.human_considered=True
        if not self.humanization or self.retries or candidate.get('requiresSoftDrop') or candidate.get('spin') or candidate.get('auto',{}).get('mode')=='survive':return []
        if any(any(row) for row in state['board'][:11]) or state['start']['y']>3:return []
        if self.rng.random()>=self.humanization/100:return []
        options=[]
        for outward,back,dx in [('L','R',-1),('R','L',1)]:
            shifted=dict(state['start'],x=state['start']['x']+dx)
            end=landing(state['board'],state['piece'],shifted)
            if end and end['y']-shifted['y']>=7:options.append([outward,back])
        return self.rng.choice(options) if options else []

    def start(self,now):
        self.pose=None
        self.enabled=True;self.phase='ready';self.reason='Waiting for piece';self.plan=None;self.waiting=None
        self.started=now+.35;self.last_seen=now;self.chain={'combo':0,'b2b':0};self.placed=0
        self.planning_key=None
        self.paused_at=None;self.retries=0
        self.hold_blocked=False;self.held_piece=None;self.verified_hold=None;self.hold_verified=False
        self.early_spawn=None
        self.recovery=None;self.revision+=1;self.failed_motion=None
        self.last_tap_at=float('-inf');self.pace_factor=1;self.human_considered=False
        self.reset_rhythm()

    def stop(self,reason='Stopped'):
        self.pose=None
        self.enabled=False;self.phase='off';self.reason=reason;self.plan=None;self.waiting=None;self.early_spawn=None;self.recovery=None;self.release()

    def resolve_pose(self,state,source,frame_at):
        """Keep true SRS orientation only when pixels support an observed move.

        I/S/Z bitmaps alias two orientations. At an unknown mid-piece start,
        restrict rotation until a new spawn, HOLD, or verified turn resolves it.
        """
        if not state or source not in ('pixels','partial','fragments'):return state
        piece=state['piece'];points=cells(piece,state['start'])
        context=(piece,state.get('generation'),tuple(state['queue']))
        pos=None;q=self.waiting
        if q and q['action'] in ('CW','CCW','180') and q.get('expected_pose') and frame_at>q['at']+.015:
            if (piece==q['piece'] and state['board']==q['board'] and state.get('generation')==q['generation']
                    and state['queue']==q['queue'] and fell_from(state['board'],piece,q['expected_pose'],points)
                    and not fell_from(state['board'],piece,q['before_pose'],points)):
                pos=pose_as(piece,points,q['expected_pose']['r'])
        if pos is None and self.pose and self.pose[0]==context:
            pos=pose_as(piece,points,self.pose[1])
        if pos is None and piece not in ('I','S','Z'):pos=dict(state['start'])
        if pos is None and min(y for x,y in points)<0:
            spawn=pose_as(piece,points,0)
            if spawn and spawn['x']==3:pos=spawn
        if pos is None:
            self.pose=None
            return {**state,'start':dict(state['start'],uncertain=True)}
        pos.pop('uncertain',None);self.pose=(context,pos['r'])
        return {**state,'start':pos}

    def resolve_hold(self,detected,known):
        # The outgoing piece becomes authoritative only after HOLD is observed.
        # A grey/occluded slot must not disable an already confirmed exchange.
        if known and not self.hold_blocked and not (self.waiting and self.waiting['action']=='HOLD'):
            if detected is not None or not self.hold_verified:
                self.verified_hold=detected;self.hold_verified=True
        return (self.verified_hold,True) if self.hold_verified else (detected,known)

    def recover(self,reason,now,reset=False,delay=.06):
        """Stay armed, discard the route, then replan from distinct fresh frames.

        Preserve pending DROP/HOLD evidence across focus/process interruptions.
        A new capture geometry invalidates even that evidence. HOLD stays blocked
        until a lock when we no longer know if this piece has used its exchange.
        """
        if not self.enabled:return
        if self.recovery is not None and not reset:return
        self.release();self.plan=None;self.early_spawn=None;self.planning_key=None
        self.thinking_done=True;self.tap_delay=0
        if reset:
            self.pose=None
            self.waiting=None;self.chain={'combo':0,'b2b':0}
            self.hold_blocked=True;self.held_piece=None
            self.verified_hold=None;self.hold_verified=False
            self.failed_motion=None
        elif self.waiting and self.waiting['action'] not in ('DROP','HOLD'):
            self.waiting=None
        self.revision+=1
        self.recovery={'after':now+max(delay,.06*min(6,max(1,self.retries))),'stamp':None,'count':0,'frame':None}
        self.phase='recover';self.reason=reason

    def resync_action(self,reason,now,state):
        q=self.waiting
        if q['action'] in ('L','R','CW','CCW','180','SD') and state['board']==q['board'] and state['piece']==q['piece'] and state['queue']==q['queue']:
            context=self.motion_context(state)
            old=self.failed_motion
            count=old['count']+1 if old and old['context']==context and old['action']==q['action'] else 1
            self.failed_motion={'context':context,'action':q['action'],'count':count}
        if q['action']=='HOLD':
            # Shift may have been ignored or its confirmation missed. Do not
            # swap again; place the actual visible piece and read HOLD afresh.
            self.hold_blocked=True;self.held_piece=None
            self.verified_hold=None;self.hold_verified=False
        if state['board']!=q.get('before_board',q['board']) or state['queue']!=q['queue']:
            self.chain={'combo':0,'b2b':0}
        self.waiting=None;self.retries+=1
        self.recover(reason,now)

    def update(self,now,state,advice,frame_at,focused,source='pixels',ambiguous=0,pause_reason=None,spawn_age_ms=None):
        if not self.enabled:return
        if now<self.started:return
        if pause_reason or not focused:
            self.pose=None
            self.early_spawn=None
            if self.paused_at is None:self.paused_at=now;self.release()
            self.phase='paused';self.reason=pause_reason or 'Game unfocused; waiting';return
        if self.paused_at is not None:
            self.paused_at=None;self.last_seen=now
            self.recovery=None
            self.recover('Focus restored; verifying field',now)
        observed=source in ('pixels','partial','fragments')
        if not state or ambiguous or source not in ('pixels','partial','fragments','next') or now-frame_at>.12:
            if self.recovery:self.recovery.update(stamp=None,count=0,frame=None)
            if now-self.last_seen>.65:
                self.phase='vision';self.reason='Pose unavailable; check field'
            return
        if observed:self.early_spawn=None
        self.last_seen=now
        if self.recovery is not None:
            r=self.recovery
            if not observed or frame_at<=r['after'] or not fits(state['board'],state['piece'],state['start']):return
            stamp=(state['board'],state['piece'],state['queue'],state.get('generation'),state['start']['x'],state['start']['r'])
            if stamp!=r['stamp'] or r['frame'] is not None and frame_at-r['frame']>.12:
                r.update(stamp=stamp,count=0,frame=None)
            if r['frame']==frame_at:return
            r['count']+=1;r['frame']=frame_at
            if r['count']<3:return
            self.recovery=None;self.revision+=1;self.phase='verify' if self.waiting else 'ready'
            self.reason='Field verified; new route'
            return
        if self.waiting:
            q=self.waiting
            if frame_at<=q['at']+.015:return
            if q['action']=='HOLD':
                if not observed:self.phase='verify';self.reason='Verifying HOLD';return
                queue_ok=q['old_hold'] is not None or state['queue'][:2]==q['queue'][1:3]
                if state['piece']==q['expected'] and queue_ok and (state['board']==q['board'] or garbage_shift(q['board'],state['board'])):
                    self.verified_hold=q['outgoing'];self.hold_verified=True
                    self.plan=None;self.waiting=None;self.planning_key=None;self.phase='ready';self.reason='HOLD confirmed; planning';return
                if now-q['at']>.7:self.resync_action('HOLD missed; using visible piece',now,state)
                return
            if q['action']=='DROP':
                # Never drop the same piece twice: await a verified new board
                # and a new active piece/preview generation.
                changed=state.get('generation')!=q['generation'] or state['queue']!=q['queue']
                if not observed:
                    n=min(3,len(q['queue'])-1,len(state['queue']))
                    known_next=n>=2 and state['piece']==q['queue'][0] and state['queue'][:n]==q['queue'][1:n+1] and state['queue']!=q['queue']
                    if not known_next:return
                if changed:
                    if state['board']==q['board'] or garbage_shift(q['board'],state['board']):
                        self.chain={k:q['chain'][k] for k in ('combo','b2b')};self.placed+=1
                        self.hold_blocked=False;self.held_piece=None;self.retries=0
                        self.human_considered=False
                        self.reset_rhythm()
                        if not observed and spawn_age_ms is not None and spawn_age_ms<=180:
                            self.early_spawn={k:state[k] for k in ('board','piece','queue','generation')}
                        self.plan=None;self.waiting=None;self.phase='ready';self.reason='Lock + NEXT confirmed' if not observed else 'Lock confirmed'
                        return
                    if not observed:self.reason='NEXT known; checking stack';return
                    # A real next-piece transition may include a garbage change
                    # the prediction cannot model. Require three distinct stable
                    # pixel frames before accepting the observed stack instead.
                    if state['queue']!=q['queue'] and q['queue'] and state['piece']==q['queue'][0]:
                        stamp=(state['board'],state['piece'],state.get('generation'),state['queue'])
                        if q.get('observed')!=stamp:q['observed']=stamp;q['stable']=0;q['frame']=None
                        if q.get('frame')!=frame_at:q['stable']+=1;q['frame']=frame_at
                        if q['stable']>=3:
                            self.chain={'combo':0,'b2b':0};self.plan=None;self.waiting=None;self.planning_key=None
                            self.hold_blocked=False;self.held_piece=None
                            self.human_considered=False
                            self.reset_rhythm()
                            self.phase='ready';self.reason='New piece; synchronizing field';return
                        self.reason='Verifying changed field';return
                    self.resync_action('Stack changed; replanning',now,state);return
            else:
                # A predicted spawn must never acknowledge our own key press.
                if not observed:self.phase='verify';self.reason='Early move; verifying pose';return
                if state['board']!=q['board'] or state['piece']!=q['piece'] or state.get('generation')!=q['generation'] or state['queue']!=q['queue']:
                    if state['piece']!=q['piece'] or state.get('generation')!=q['generation'] or state['queue']!=q['queue']:self.reset_rhythm()
                    self.plan=None;self.waiting=None;self.phase='ready';self.reason='Field changed; replanning';return
                actual=cells(state['piece'],state['start']);before=q['cells']
                if q['action'] in ('CW','CCW','180') and q.get('expected_pose'):
                    if (fell_from(state['board'],state['piece'],q['expected_pose'],actual)
                            and not fell_from(state['board'],state['piece'],q['before_pose'],actual)):
                        self.pose=((state['piece'],state.get('generation'),tuple(state['queue'])),q['expected_pose']['r'])
                        self.plan['index']+=1;self.waiting=None;self.phase='moving';self.retries=0;self.failed_motion=None;return
                    if now-q['at']>.45:self.resync_action('Rotation unconfirmed; replanning',now,state)
                    return
                if q['action']=='SD':
                    target=q['target']
                    if actual==target:
                        self.plan['index']+=1;self.waiting=None;self.retries=0;self.phase='moving';return
                    same_column=min(x for x,y in actual)==min(x for x,y in before) and self.shape(actual)==self.shape(before)
                    if not same_column or min(y for x,y in actual)>min(y for x,y in target):
                        self.resync_action('Descent changed; replanning',now,state);return
                    if min(y for x,y in actual)>min(y for x,y in before):
                        self.waiting=None;self.phase='moving';self.reason='Descending to surface';return
                if actual!=before:
                    oldx=min(x for x,y in before);newx=min(x for x,y in actual)
                    if q['action'] in ('L','R'):
                        delta=-1 if q['action']=='L' else 1
                        valid=newx-oldx==delta and self.shape(actual)==self.shape(before)
                    else:
                        # The bitmap cannot disambiguate 0/2 of I/S/Z. Compare
                        # the rotated normalized shape, allowing wall kicks.
                        target=(q['rotation']+(2 if q['action']=='180' else 1 if q['action']=='CW' else -1))%4
                        valid=self.shape(actual)==self.shape(SHAPES[q['piece']][target])
                    if valid:
                        self.plan['index']+=1;self.waiting=None;self.phase='moving';self.retries=0;self.failed_motion=None;return
            if now-q['at']>.45:
                self.resync_action(q['action']+' unconfirmed; replanning',now,state)
            return
        early=not observed and self.early_spawn is not None and all(state.get(k)==v for k,v in self.early_spawn.items()) and spawn_age_ms is not None and spawn_age_ms<=180
        if not observed and not early:
            self.phase='vision';self.reason=f"{state['piece']} from NEXT; waiting for pose";return
        if self.plan and (state['board']!=self.plan['board'] or state['piece']!=self.plan['piece']):
            self.plan=None;self.reason='Stack changed; replanning'
        if (self.plan and not self.plan.get('inTuck') and not self.deep_replanned and observed and state['start']['y']<=3
                and advice and advice['state']==state and advice['stage']=='final'
                and advice['candidate'].get('lookahead',1)>self.plan.get('lookahead',1)):
            self.plan=None;self.deep_replanned=True;self.reason='Deeper attack route ready'
        if not self.plan:
            if state.get('controllerRevision',self.revision)!=self.revision:return
            if not advice or advice['state']!=state:return
            if state.get('chain',self.chain)!=self.chain:return
            planning_key=(tuple(tuple(r) for r in state['board']),state['piece'],state.get('generation'))
            if planning_key!=self.planning_key:self.planning_key=planning_key;self.planning_at=now
            wait_budget=.02 if advice['candidate'].get('auto',{}).get('mode')=='survive' else .04
            if advice['stage'] in ('fast','refined') and now-self.planning_at<wait_budget:
                self.reason='Refining with NEXT';return
            c=advice['candidate']
            failed=self.failed_motion
            if failed and failed['count']>=2 and failed['context']==self.motion_context(state):
                # If the same observed move fails twice, try another reachable
                # placement whose first action avoids that move/rotation.
                for alternative in advice.get('candidates',[]):
                    first='HOLD' if alternative.get('useHold') else next((a for a in alternative['path'] if a!='D'),'DROP')
                    if first!=failed['action']:
                        c=alternative;break
            if not self.pace_ready(now,state,c,observed):return
            path=list(c['path'])
            if c.get('useHold'):
                if self.hold_blocked or not state.get('allowHold') or state.get('canHold') is False:return
                expected=state.get('hold') or (state['queue'][0] if state['queue'] else None)
                if not expected or expected==state['piece']:return
                if not self.send('HOLD',now):self.recover('HOLD input failed; replanning',now);return
                self.early_spawn=None
                self.hold_blocked=True;self.held_piece=state['piece']
                self.waiting={'action':'HOLD','at':now,'expected':expected,'outgoing':state['piece'],'old_hold':state.get('hold'),'board':state['board'],'queue':state['queue']}
                self.phase='verify';self.reason='Verifying HOLD';return
            while path and path[-1] in ('D','SD'):path.pop()
            if any(a not in ('L','R','CW','CCW','180','SD') for a in path):self.reason='Waiting for an executable route';return
            route=c.get('route',[])
            if any(a in path for a in ('SD','180')) and (len(route)<len(path) or any(step.get('action')!=action for step,action in zip(route,path))):
                self.reason='Waiting for descent checkpoints';return
            if '180' in path and (not self.vk.get('180') or state.get('allow180') is False):
                self.reason='180 rotation disabled; replanning';return
            prefix=self.human_prefix(state,c,observed)
            self.plan={'piece':state['piece'],'board':state['board'],'target':cells(c['piece'],c['pos']),
                       'actions':prefix+path+['DROP'],'human_prefix':len(prefix),'index':0,'result':c['board'],'chain':c.get('chain',{'combo':0,'b2b':0}),
                       'origin':dict(state['start']),'route':([None]*len(prefix))+route[:len(path)],'requiresSoftDrop':c.get('requiresSoftDrop',False),'spin':c.get('spin'),
                       'lookahead':c.get('lookahead',1),
                       'auto':c.get('auto',{}),'intent':c.get('intent'),'comboPlan':c.get('comboPlan',0),
                       'pcVerified':c.get('pcVerified',False),'pcPieces':c.get('pcPieces',0),'attackPlan':c.get('attackPlan',0),
                       'attackPriority':c.get('attackPriority',False)}
        p=self.plan;action=p['actions'][p['index']]
        expected_pose=None
        if action=='SD':p['inTuck']=True
        if not self.pace_ready(now,state,p,observed):return
        if action in ('CW','CCW','180') and len(p['route'])>p['index'] and p['route'][p['index']]:
            previous=p['route'][p['index']-1] if p['index'] else None
            before=previous['pos'] if previous else p['origin']
            actual=state['start'];fall=actual['y']-before['y']
            if actual.get('uncertain') or actual['x']!=before['x'] or actual['r']!=before['r'] or fall<0:
                self.plan=None;self.reason='Orientation changed; replanning';return
            expected_pose=dict(p['route'][p['index']]['pos']);expected_pose['y']+=fall
            if not fits(state['board'],state['piece'],expected_pose):
                self.plan=None;self.reason='Rotation surface changed; replanning';return
        if action=='SD':
            if not observed:self.phase='vision';self.reason='Verifying pose before descent';return
            target=cells(p['piece'],p['route'][p['index']]['pos'])
            landed=landing(state['board'],state['piece'],state['start'])
            if not landed or cells(state['piece'],landed)!=target:
                self.plan=None;self.reason='Surface changed; replanning';return
            if cells(state['piece'],state['start'])==target:
                p['index']+=1;return
        if p['index']<p.get('human_prefix',0):
            shifted=dict(state['start'],x=state['start']['x']+(-1 if action=='L' else 1))
            if not observed or not fits(state['board'],state['piece'],shifted):
                self.recover('Sidestep blocked; replanning',now);return
        if action=='DROP':
            if not observed:self.phase='vision';self.reason='Verifying pose before DROP';return
            landed=landing(state['board'],state['piece'],state['start'])
            if not landed or cells(state['piece'],landed)!=p['target']:
                self.plan=None;self.reason='Pose changed; replanning DROP';return
        if not self.send(action,now):self.recover('Input failed; replanning',now);return
        self.early_spawn=None
        self.waiting={'action':action,'at':now,'piece':state['piece'],'cells':cells(state['piece'],state['start']),
                      'rotation':state['start']['r'],'board':p['result'] if action=='DROP' else state['board'],
                      'queue':state['queue'],'generation':state.get('generation'),'chain':p['chain'],'before_board':state['board']}
        if action=='SD':self.waiting['target']=target
        if expected_pose:self.waiting.update(expected_pose=expected_pose,before_pose=dict(state['start']))
        self.phase='verify';self.reason=('Early NEXT move: ' if early else 'Verifying ')+action

    @staticmethod
    def motion_context(state):
        return (state['board'],state['piece'],state['queue'],state['start']['x'],state['start']['r'])

    @staticmethod
    def shape(points):
        mx=min(x for x,y in points);my=min(y for x,y in points)
        return sorted((x-mx,y-my) for x,y in points)
