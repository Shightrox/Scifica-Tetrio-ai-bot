"""No real keyboard input. Model feedback and faults at individual key boundaries."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from autoplay import AutoPlayer, landing, cells
import preferences

class PredictableRandom:
    def random(self): return 0
    def choice(self,items): return items[0]
    def uniform(self,a,b): return b

def scene(x=3,y=-2):
    return dict(board=[[None]*10 for _ in range(20)],piece='T',start=dict(x=x,y=y,r=0),
                queue=['I','O','S'],generation=1)

def advice(state,path=None,dx=0):
    pos=landing(state['board'],state['piece'],dict(state['start'],x=state['start']['x']+dx))
    board=copy.deepcopy(state['board'])
    for x,y in cells('T',pos): board[y][x]='T'
    return dict(state=state,stage='final',candidate=dict(piece='T',path=path or [],pos=pos,board=board,auto={'mode':'attack'}))

class ControllerTests(unittest.TestCase):
    def bot(self,rate=30,human=100):
        keys=[];bot=AutoPlayer(lambda key:keys.append(key) or True,rng=PredictableRandom())
        bot.configure(rate,human);bot.start(0)
        return bot,keys
    def test_feedback_pair_then_exact_drop(self):
        b,keys=self.bot();s=scene();a=advice(s)
        b.update(.4,s,a,.4,True);self.assertEqual(keys,[0x25])
        b.update(.5,s,a,.5,True);self.assertEqual(keys,[0x25]) # no blind correction
        moved={**s,'start':dict(s['start'],x=2,y=-1)} # gravity during first tap
        b.configure(30,0) # disabling cosmetics must still finish pending correction
        b.update(.6,moved,None,.6,True);self.assertIsNone(b.waiting)
        b.update(.7,moved,None,.7,True);self.assertEqual(keys,[0x25,0x27])
        returned={**s,'start':dict(s['start'],y=-1)}
        b.update(.8,returned,None,.8,True)
        b.update(.9,returned,None,.9,True);self.assertEqual(keys,[0x25,0x27,0x20])
        b.update(1.,returned,None,1.,True);self.assertEqual(keys,[0x25,0x27,0x20])
    def test_tempo_does_not_delay_ack_or_focus_guard(self):
        b,keys=self.bot(2,0);s=scene();a=advice(s,['L'],dx=-1)
        b.update(.4,s,a,.4,True)
        moved={**s,'start':dict(s['start'],x=2)}
        b.update(.44,moved,None,.44,True);self.assertIsNone(b.waiting)
        b.update(.5,moved,None,.5,True);self.assertEqual(b.phase,'pacing')
        self.assertEqual(keys,[0x25])
        b.configure(30,0);b.update(.6,moved,None,.6,False)
        self.assertEqual(b.phase,'paused');self.assertEqual(keys,[0x25])
    def test_slower_rate_caps_taps_and_max_applies_live(self):
        b,keys=self.bot(2,0);s=scene();b.update(.4,s,advice(s,['L'],dx=-1),.4,True)
        moved={**s,'start':dict(s['start'],x=2)}
        b.update(.44,moved,None,.44,True)
        b.update(.89,moved,None,.89,True);self.assertEqual(len(keys),1)
        b.configure(30,0);b.update(.90,moved,None,.90,True);self.assertEqual(keys,[0x25,0x20])
    def test_ignored_movement_recovers_without_blind_return(self):
        for ignore_return in (False,True):
            b,keys=self.bot();s=scene();b.update(.4,s,advice(s),.4,True)
            if ignore_return:
                s={**s,'start':dict(s['start'],x=2)}
                b.update(.44,s,None,.44,True);b.update(.5,s,None,.5,True)
            b.update(1.1,s,None,1.1,True)
            self.assertEqual(b.phase,'recover');self.assertTrue(b.enabled)
            self.assertNotIn(0x20,keys)
            for at in (1.2,1.24,1.28,1.32): b.update(at,s,advice(s),at,True)
            self.assertEqual(keys.count(0x25),1)
            self.assertFalse(b.plan and b.plan['human_prefix'])
    def test_cosmetics_excluded_for_risk_or_inference(self):
        for kind in ('off','survive','high','low','next','retry'):
            b,_=self.bot();s=scene();c=advice(s)['candidate'];observed=True
            if kind=='off':b.configure(30,0)
            if kind=='survive':c['auto']['mode']='survive'
            if kind=='high':s['board'][10][0]='J'
            if kind=='low':s['start']['y']=10
            if kind=='next':observed=False
            if kind=='retry':b.retries=1
            self.assertEqual(b.human_prefix(s,c,observed),[],kind)
        b,_=self.bot();s=scene(x=0)
        self.assertEqual(b.human_prefix(s,advice(s)['candidate'],True),['R','L'])
        self.assertEqual(b.human_prefix(s,advice(s)['candidate'],True),[])
    def test_changed_stack_and_stop_cancel_cosmetic_route(self):
        b,keys=self.bot();s=scene();b.update(.4,s,advice(s),.4,True)
        changed=copy.deepcopy(s);changed['board'][19][1]='G'
        b.update(.5,changed,None,.5,True);self.assertIsNone(b.plan)
        b.stop();b.update(.8,s,advice(s),.8,True);self.assertEqual(keys,[0x25])
    def test_focus_loss_mid_detour_replans_from_observed_position(self):
        b,keys=self.bot();s=scene();b.update(.4,s,advice(s),.4,True)
        moved={**s,'start':dict(s['start'],x=2)}
        b.update(.44,moved,None,.44,True)
        b.update(.48,moved,None,.48,False)
        b.update(.6,moved,advice(moved),.6,True)
        self.assertIsNone(b.plan);self.assertEqual(keys,[0x25])
        for at in (.7,.74,.78,.82):b.update(at,moved,advice(moved),at,True)
        self.assertEqual(keys,[0x25,0x20])
        self.assertEqual(b.plan['human_prefix'],0)
    def test_clearance_and_stale_frames_block_extra_taps(self):
        b,keys=self.bot();s=scene(y=3);s['board'][11]=['G']*10
        self.assertEqual(b.human_prefix(s,advice(s)['candidate'],True),[])
        b,_=self.bot();s=scene();b.update(.4,s,advice(s),.1,True)
        self.assertIsNone(b.plan)
    def test_preferences_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.json'
            self.assertEqual(preferences.load(path),preferences.DEFAULTS)
            preferences.save(path,dict(key_rate=11,humanization=37,use_hold=False,swap_rotation=True))
            data=preferences.load(path);self.assertEqual(data['key_rate'],11);self.assertFalse(data['use_hold'])
            path.write_text('{broken');self.assertEqual(preferences.load(path),preferences.DEFAULTS)
            self.assertEqual(preferences.sanitize({'key_rate':float('nan'),'humanization':float('inf')}),preferences.DEFAULTS)

if __name__=='__main__':unittest.main()
