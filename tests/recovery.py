"""Fault injection against the real planner/controller; all game input is mocked."""
import copy,json,queue,subprocess,sys,threading,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from autoplay import AutoPlayer,cells,landing
from overlay import Overlay
NODE='node'
def blank():return [[None]*10 for _ in range(20)]

rpc_process=subprocess.Popen([NODE,str(Path(__file__).with_name('engine-rpc.cjs'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
def rpc(v):
    rpc_process.stdin.write(json.dumps(v)+'\n');rpc_process.stdin.flush()
    return json.loads(rpc_process.stdout.readline())

try:
    state={'board':blank(),'piece':'O','start':{'x':4,'y':-2,'r':0},'hold':'I',
           'queue':['T','S','Z','L','J','O','I']*40,'generation':0,'simpleOnly':True,
           'profile':'versus','allowHold':True,'depth':2}
    for y in range(16,20):state['board'][y]=['G']*9+[None]
    faults={'ignored_move':0,'ignored_hold':0,'ignored_drop':0,'refused_input':0,'focus':0,'vision':0,'garbage':0}
    sent=[];pause_ticks=0;blind_ticks=0;holds_this_piece=0
    def tap(vk):
        global state,pause_ticks,holds_this_piece
        sent.append(vk);s=state
        if vk==0x10:
            if not faults['ignored_hold']:faults['ignored_hold']=1;return True
            holds_this_piece+=1;assert holds_this_piece==1,'double HOLD in one placement'
            t=s['hold'] or s['queue'][0]
            state={**s,'piece':t,'hold':s['piece'],'queue':s['queue'] if s['hold'] else s['queue'][1:],
                   'start':{'x':4 if t=='O' else 3,'y':-2,'r':0}}
        elif vk==0x20:
            if not faults['ignored_drop']:faults['ignored_drop']=1;return True
            placed=rpc({'op':'drop','board':s['board'],'piece':s['piece'],'pos':s['start']})
            assert placed and placed.get('board') is not None
            t=s['queue'][0]
            state={**s,'board':placed['board'],'piece':t,'queue':s['queue'][1:],
                   'start':{'x':4 if t=='O' else 3,'y':-2,'r':0},'generation':s['generation']+1}
            holds_this_piece=0
            if not faults['focus']:faults['focus']=1;pause_ticks=5
        else:
            if faults['ignored_move']<4:faults['ignored_move']+=1;return True
            if not faults['refused_input']:faults['refused_input']=1;return False
            action={0x25:'L',0x27:'R',0x58:'CW',0x5a:'CCW'}[vk]
            pos=rpc({'op':'move','board':s['board'],'piece':s['piece'],'pos':s['start'],'action':action})
            assert pos
            state={**s,'start':pos}
            if bot.placed>=8 and not faults['garbage']:
                faults['garbage']=1;row=['G']*10;row[4]=None
                state={**state,'board':state['board'][2:]+[row[:],row[:]],'generation':state['generation']+1}
        return True
    bot=AutoPlayer(tap);bot.start(0);now=.4
    for tick in range(2600):
        state={**state,'chain':dict(bot.chain),'canHold':not bot.hold_blocked,'controllerRevision':bot.revision}
        result=rpc({'op':'analyze','state':state});assert result.get('candidates'),(bot.reason,state)
        advice={'state':state,'stage':'final','candidate':result['candidates'][0]}
        if bot.placed>=10 and not faults['vision']:faults['vision']=1;blind_ticks=20
        focused=pause_ticks==0;ambiguous=1 if blind_ticks else 0
        count=len(sent)
        bot.update(now,state,advice,now-.005,focused,ambiguous=ambiguous)
        assert bot.enabled,bot.reason
        if not focused or ambiguous:assert len(sent)==count
        pause_ticks=max(0,pause_ticks-1);blind_ticks=max(0,blind_ticks-1);now+=.04
        if bot.placed>=60:break
    assert bot.placed>=60 and all(faults.values()),(bot.placed,faults,bot.reason)
    print('PASS 60 placements through faults:',faults,'keys',len(sent))

    # Late HOLD response after timeout is accepted as a new visible position;
    # even stale HOLD advice cannot send a second Shift.
    s={'board':blank(),'piece':'T','start':{'x':3,'y':-2,'r':0},'queue':['I','O','J'],
       'generation':0,'hold':'S','allowHold':True,'canHold':True}
    keys=[];b=AutoPlayer(lambda vk:keys.append(vk) or True);b.start(0)
    advice={'state':s,'stage':'final','candidate':{'useHold':True,'path':[]}}
    b.update(.4,s,advice,.4,True);b.update(1.2,s,None,1.2,True)
    late={**s,'piece':'S','hold':'T','generation':4}
    for at in (1.3,1.32,1.34,1.36):b.update(at,late,dict(advice,state=late),at,True)
    assert b.enabled and not b.recovery and b.hold_blocked and keys==[0x10]
    # Stop cancels a pending automatic recovery permanently until re-armed.
    b.recover('test',2);b.stop('Escape')
    for at in (3,3.1,3.2,4):b.update(at,late,advice,at,True)
    assert not b.enabled and keys==[0x10]
    print('PASS delayed HOLD, stale advice blocked, explicit stop cancels recovery')

    # An uncertain DROP is not retried using an old or duplicate frame, an
    # inferred NEXT spawn, or frames on opposite sides of a recognition gap.
    keys=[];b=AutoPlayer(lambda vk:keys.append(vk) or True);b.start(0)
    c=rpc({'op':'analyze','state':{**s,'allowHold':False,'simpleOnly':True}})['candidates'][0]
    c.update(path=[],pos=landing(s['board'],s['piece'],s['start']))
    a={'state':s,'stage':'final','candidate':c}
    b.update(.4,s,a,.4,True);assert keys==[0x20]
    b.update(1,s,None,1,True);assert b.phase=='recover'
    for at in (1.1,1.12,1.14):b.update(at,s,a,1.1,True)
    for at in (1.16,1.18):b.update(at,s,a,at,True,'next',spawn_age_ms=10)
    b.update(1.2,None,None,1.2,True)
    b.update(1.22,s,a,1.22,True);b.update(1.24,s,a,1.24,True)
    assert keys==[0x20] and b.recovery
    b.update(1.26,s,a,1.26,True);assert not b.recovery and keys==[0x20]
    b.update(1.28,s,a,1.28,True);assert keys==[0x20,0x20]
    print('PASS DROP recovery requires three fresh observed frames and a revalidated landing')

    # A permanently ineffective left key must not pin the bot to that route.
    keys=[];b=AutoPlayer(lambda vk:keys.append(vk) or True);b.start(0)
    left=dict(c,path=['L'],pos=landing(s['board'],s['piece'],dict(s['start'],x=2)))
    right=dict(c,path=['R'],pos=landing(s['board'],s['piece'],dict(s['start'],x=4)))
    alternatives={'state':s,'stage':'final','candidate':left,'candidates':[left,right]}
    for step in range(100):
        at=.4+step*.04;b.update(at,s,alternatives,at,True)
        if 0x27 in keys:break
    assert keys==[0x25,0x25,0x27] and b.enabled,keys
    print('PASS two failed left moves select an alternative placement starting right')
finally:
    rpc_process.stdin.close();rpc_process.wait(timeout=5)

# Kill only the test-owned solver; use real transport/restart handlers without UI.
app=Overlay.__new__(Overlay)
app.node=NODE;app.solver_generation=0;app.solver_retry_at=None;app.solver_failures=0
app.stop=threading.Event();app.answers=queue.Queue();app.serial=0
app.player=AutoPlayer(lambda vk:True);app.player.start(0)
app.status=SimpleNamespace(set=lambda text:None)
app.start_solver();old_process=app.solver
try:
    old_process.terminate();old_process.wait(timeout=3)
    failure=app.answers.get(timeout=3);assert failure['stage']=='fatal'
    app.solver_failed(time.perf_counter(),failure['error'])
    assert app.player.enabled and app.solver_retry_at is not None
    app.start_solver();assert app.solver_generation!=failure['worker']
    state={'board':blank(),'piece':'T','start':{'x':3,'y':-2,'r':0},'queue':['I'],'simpleOnly':True}
    key=json.dumps(state,separators=(',',':'));app.current_key=key;app.pending=(state,key,time.perf_counter())
    app.send_pending();answer=app.answers.get(timeout=5)
    assert answer['worker']==app.solver_generation and answer['result']['candidates']
    assert app.player.enabled
    print('PASS actual solver process restart, new result, old worker messages identifiable, autoplay remains armed')
finally:
    app.stop.set();app.solver.terminate();app.solver.wait(timeout=3)
