"""Pixel feedback for the new rotation routes; all key delivery is mocked."""
import copy,json,subprocess,unittest
from pathlib import Path
from autoplay import AutoPlayer,cells
from overlay_vision import Reader,fit_active,TYPES
from vision_fixture import scene,blank
import preferences

ROOT=Path(__file__).resolve().parents[1]

class RotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rpc=subprocess.Popen(['node',str(ROOT/'tests/engine-rpc.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        cls.samples=json.loads((ROOT/'tests/rotation-cases.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.rpc.stdin.close();cls.rpc.wait(timeout=10);cls.rpc.stdout.close()

    def call(self,value):
        self.rpc.stdin.write(json.dumps(value)+'\n');self.rpc.stdin.flush()
        return json.loads(self.rpc.stdout.readline())

    def run_route(self,sample,miss=False,partial=False):
        board=blank()
        for i,row in enumerate(sample['rows']):board[20-len(sample['rows'])+i]=['T' if v=='X' else None for v in row]
        state=dict(board=board,piece=sample['piece'],start=dict(x=3,y=-2,r=0),queue=['O','L','S','Z','I'],hold=None,
                   generation=0,simpleOnly=True,tucks=True,rotationSystem='srs+',allow180=True,allowHold=False)
        target=cells(state['piece'],sample['target'])
        candidate=next(p for p in self.call(dict(op='placements',state=state)) if cells(p['piece'],p['pos'])==target)
        candidate['chain']=dict(combo=1,b2b=1)
        keys=[];faults=[]
        def tap(key):
            nonlocal state
            keys.append(key)
            if key==0x20:
                self.assertFalse(miss,'a missed final turn must not lead to a drop')
                locked=self.call(dict(op='drop',board=state['board'],piece=state['piece'],pos=state['start']))
                self.assertEqual(locked['lines'],sample.get('lines',1));self.assertEqual(locked['board'],candidate['board'])
                state={**state,'board':locked['board'],'piece':'O','start':dict(x=4,y=-2,r=0),'queue':['L','S','Z','I','T'],'generation':1}
            else:
                action={0x25:'L',0x27:'R',0x58:'CW',0x5a:'CCW',0x28:'SD',0x41:'180'}[key]
                if miss and bot.plan['index']==len(candidate['path'])-1:
                    faults.append(action);return True
                pos=self.call(dict(op='move',board=state['board'],piece=state['piece'],pos=state['start'],action=action,rotationSystem='srs+'))
                self.assertIsNotNone(pos)
                if action=='SD' and partial:pos['y']=min(pos['y'],state['start']['y']+2)
                state={**state,'start':pos}
            return True
        bot=AutoPlayer(tap);bot.start(0);reader=Reader()
        for step in range(180):
            now=.4+step*.025
            v=reader.read(scene(state['board'],state['piece'],state['start'],state['queue']),200,400,top=80,action=bot.waiting)
            self.assertTrue(v['active'] and not v['ambiguous'],(step,v))
            observed={**state,'board':v['board'],'start':v['active']['start'],'chain':dict(bot.chain)}
            observed=bot.resolve_pose(observed,v['source'],now)
            self.assertEqual(observed['start']['r'],state['start']['r'],(step,state['start'],observed['start']))
            answer=dict(state=observed,candidate=candidate,stage='final') if step==0 else None
            bot.update(now,observed,answer,now,True,source=v['source'])
            if bot.placed or bot.recovery:break
        if miss:
            self.assertTrue(bot.recovery);self.assertTrue(faults);self.assertNotIn(0x20,keys)
        else:
            self.assertEqual(bot.placed,1,(keys,bot.reason));self.assertEqual(keys.count(0x20),1)
            if sample['piece']=='J':self.assertIn(0x41,keys)
        return keys

    def test_pixel_verified_half_turn_and_i_tuck(self):
        for sample in self.samples:
            for partial in (False,True):
                with self.subTest(piece=sample['piece'],partial=partial):self.run_route(sample,partial=partial)

    def test_missed_half_turn_and_i_kick_recover_without_drop(self):
        for sample in self.samples:
            with self.subTest(piece=sample['piece']):self.run_route(sample,miss=True)

    def test_s_and_z_tucks_keep_reverse_orientation_through_pixels(self):
        for piece,x in (('S',1),('Z',5)):
            sample=dict(piece=piece,rows=self.samples[1]['rows'],target=dict(x=x,y=16,r=2),lines=0)
            with self.subTest(piece=piece):self.run_route(sample)

    def test_symmetric_rotation_state_survives_canonical_pixels(self):
        for piece in ('I','S','Z'):
            board=blank();true=dict(x=3,y=5,r=2)
            raw=fit_active(cells(piece,true),TYPES.index(piece))['start']
            self.assertEqual(raw['r'],0)
            state=dict(board=board,piece=piece,start=raw,queue=['T','O'],generation=4)
            bot=AutoPlayer(lambda key:True);bot.pose=((piece,4,('T','O')),2)
            self.assertEqual(bot.resolve_pose(state,'pixels',1)['start'],true)
            bot.stop()
            self.assertTrue(bot.resolve_pose(state,'pixels',2)['start']['uncertain'])

    def test_gravity_cannot_acknowledge_symmetric_180(self):
        state=dict(board=blank(),piece='I',start=dict(x=3,y=4,r=0),queue=['T','O'],generation=2)
        bot=AutoPlayer(lambda key:True);bot.start(0)
        bot.plan=dict(index=0)
        bot.waiting=dict(action='180',at=.4,piece='I',cells=cells('I',dict(x=3,y=3,r=0)),
                         before_pose=dict(x=3,y=3,r=0),expected_pose=dict(x=3,y=3,r=2),
                         board=state['board'],queue=state['queue'],generation=2,rotation=0)
        bot.update(.45,state,None,.45,True)
        self.assertIsNotNone(bot.waiting);self.assertEqual(bot.plan['index'],0)
        bot.update(1.,state,None,1.,True);self.assertTrue(bot.recovery)

    def test_binding_migration_off_and_invalid_values(self):
        self.assertEqual(preferences.sanitize({})['rotation_180'],'A')
        self.assertEqual(preferences.sanitize({'rotation_180':'Off'})['rotation_180'],'Off')
        for value in ([],{},7,'Space','Z'):
            self.assertEqual(preferences.sanitize({'rotation_180':value})['rotation_180'],'A')

if __name__=='__main__':unittest.main()
