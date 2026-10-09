"""Real planner -> pixels -> controller -> mocked key sink; no real game input."""
import copy,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from autoplay import AutoPlayer
from overlay_vision import Reader
from vision_fixture import scene,blank
rpc_process=subprocess.Popen(['node',str(Path(__file__).with_name('engine-rpc.cjs'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
def rpc(value):
    rpc_process.stdin.write(json.dumps(value)+'\n');rpc_process.stdin.flush()
    return json.loads(rpc_process.stdout.readline())
try:
 for partial_drop in (False,True):
    board=blank();board[17][3]='J'
    board[18]=[None if x=='.' else 'J' for x in 'XXX...XXXX']
    board[19]=[None if x=='.' else 'J' for x in 'XXXX.XXXXX']
    state=dict(board=board,piece='T',start=dict(x=3,y=-2,r=0),queue=['I','S','O','J','Z'],hold=None,generation=0,
               allowHold=False,canHold=True,simpleOnly=True,tucks=True,profile='versus',attackPriority=True)
    keys=[];rotations=[]
    def tap(vk):
        global state
        keys.append(vk)
        if vk==0x20:
            locked=rpc(dict(op='drop',board=state['board'],piece=state['piece'],pos=state['start']))
            assert locked['lines']==2,'must finish the T-spin double, not drop on its roof'
            state={**state,'board':locked['board'],'piece':'I','start':dict(x=3,y=-2,r=0),'queue':['S','O','J','Z','L'],'generation':1}
        else:
            a={0x25:'L',0x27:'R',0x58:'CW',0x5a:'CCW',0x28:'SD'}[vk]
            pos=rpc(dict(op='move',board=state['board'],piece=state['piece'],pos=state['start'],action=a))
            assert pos
            if a=='SD' and partial_drop:pos['y']=min(pos['y'],state['start']['y']+3)
            if a in ('CW','CCW'):rotations.append(pos['y'])
            state={**state,'start':pos}
        return True
    bot=AutoPlayer(tap);bot.configure(2,100,100);bot.start(0);reader=Reader()
    for step in range(250):
        now=.4+step*.025
        vision=reader.read(scene(state['board'],state['piece'],state['start'],state['queue']),200,400,top=80,action=bot.waiting)
        assert vision['active'] and not vision['ambiguous'],(step,vision)
        observed={**state,'board':vision['board'],'start':vision['active']['start'],'chain':dict(bot.chain)}
        result=rpc(dict(op='analyze',state=observed))
        candidate=result['candidates'][0]
        bot.update(now,observed,dict(state=observed,candidate=candidate,stage='final'),now,True)
        if bot.placed:break
    assert bot.placed==1 and keys.count(0x20)==1,(keys,bot.reason)
    assert rotations[-1]>=16 and 0x28 in keys
    assert bot.chain['b2b']==1
    print('PASS pixel-verified T-spin double; partial descent:',partial_drop,'keys:',len(keys))
finally:
 rpc_process.stdin.close();rpc_process.wait(timeout=10)
