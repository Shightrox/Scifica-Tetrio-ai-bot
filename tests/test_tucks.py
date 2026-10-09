import json,subprocess,unittest
from pathlib import Path
from autoplay import AutoPlayer
from test_controller import scene

class TuckControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]
        cls.rpc=subprocess.Popen(['node',str(root/'tests/engine-rpc.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)

    @classmethod
    def tearDownClass(cls):
        cls.rpc.stdin.close();cls.rpc.wait(timeout=10);cls.rpc.stdout.close()

    def call(self,value):
        self.rpc.stdin.write(json.dumps(value)+'\n');self.rpc.stdin.flush()
        return json.loads(self.rpc.stdout.readline())

    def setup_bot(self,hold=None,release=lambda:None):
        state={**scene(),'simpleOnly':True,'tucks':True,'profile':'versus','attackPriority':True,'allowHold':False}
        state['board'][17][3]='J'
        state['board'][18]=[None if v=='.' else 'J' for v in 'XXX...XXXX']
        state['board'][19]=[None if v=='.' else 'J' for v in 'XXXX.XXXXX']
        c=self.call(dict(op='analyze',state=state))['candidates'][0]
        keys=[];bot=AutoPlayer(lambda key:keys.append(key) or True,release,soft_drop=hold);bot.start(0)
        bot.update(.4,state,dict(state=state,candidate=c,stage='final'),.4,True)
        self.assertEqual(keys,[0x58])
        moved={**state,'start':c['route'][0]['pos']}
        bot.update(.44,moved,None,.44,True);bot.update(.48,moved,None,.48,True)
        self.assertEqual(keys,[0x58] if hold else [0x58,0x28])
        return bot,keys,moved,c

    def test_held_descent_tracks_progress_then_releases_before_spin(self):
        events=[]
        bot,keys,state,c=self.setup_bot(lambda:events.append('hold') or True,lambda:events.append('up'))
        self.assertEqual(events,['hold'])
        now=.48
        # Slow soft drop can take longer than the old total 450 ms timeout.
        # Each new downward observation resets only the progress timeout.
        for y in range(state['start']['y']+1,c['route'][1]['pos']['y']+1):
            now+=.08;state={**state,'start':dict(state['start'],y=y)}
            bot.update(now,state,None,now,True)
            self.assertFalse(bot.recovery)
        self.assertGreater(now,.93)
        self.assertEqual(events[-1],'up');self.assertIsNone(bot.waiting)
        bot.update(now+.025,state,None,now+.025,True)
        self.assertEqual(keys,[0x58,0x58],'surface turn only after releasing Down')
        spun={**state,'start':c['route'][2]['pos']}
        bot.update(now+.05,spun,None,now+.05,True)
        bot.update(now+.075,spun,None,now+.075,True)
        self.assertEqual(keys,[0x58,0x58,0x20])

    def test_held_descent_releases_on_vision_focus_and_board_changes(self):
        for fault in ('missing','stale','next','ambiguous','focus','board','generation','stop'):
            events=[]
            bot,keys,state,c=self.setup_bot(lambda:events.append('hold') or True,lambda:events.append('up'))
            if fault=='board':
                state={**state,'board':[row[:] for row in state['board']]};state['board'][16][4]='G'
            if fault=='generation':state={**state,'generation':2}
            if fault=='stop':bot.stop()
            else:bot.update(.65,None if fault=='missing' else state,None,.48 if fault=='stale' else .65,
                            fault!='focus',source='next' if fault=='next' else 'pixels',ambiguous=int(fault=='ambiguous'))
            self.assertEqual(events,['hold','up'],fault)
            self.assertEqual(keys,[0x58],fault)

    def test_held_descent_needs_distinct_frames_and_actual_progress(self):
        events=[]
        bot,keys,state,c=self.setup_bot(lambda:events.append('hold') or True,lambda:events.append('up'))
        bot.update(.51,state,None,.51,True)
        bot.update(.52,state,None,.51,True)
        self.assertEqual(events,['hold','hold'],'duplicate frames cannot extend the hold lease')
        bot.update(.95,state,None,.95,True)
        self.assertTrue(bot.recovery);self.assertEqual(events[-1],'up')
        self.assertEqual(keys,[0x58])

    def test_turn_above_grid_then_space_without_waiting_for_gravity(self):
        state={**scene(),'simpleOnly':True,'tucks':True,'rotationSystem':'srs+','allow180':True}
        c=next(c for c in self.call(dict(op='placements',state=state))
               if c['pos']['r']==1 and c['pos']['x']==3 and c['path']==['CW','SD'])
        keys=[];bot=AutoPlayer(lambda key:keys.append(key) or True);bot.start(0)
        bot.update(.4,state,dict(state=state,candidate=c,stage='final'),.4,True)
        self.assertEqual(keys,[0x58])
        moved={**state,'start':c['route'][0]['pos']}
        self.assertEqual(moved['start']['y'],-2)
        bot.update(.425,moved,None,.425,True)
        bot.update(.433,moved,None,.433,True)
        self.assertEqual(keys,[0x58,0x20],'terminal SD is replaced by hard drop from spawn height')

    def test_ignored_descent_replans_without_rotation_or_drop(self):
        bot,keys,state,c=self.setup_bot()
        bot.update(1.,state,None,1.,True)
        self.assertTrue(bot.recovery);self.assertIsNone(bot.plan)
        self.assertEqual(keys,[0x58,0x28])

    def test_missed_low_rotation_cannot_hard_drop(self):
        bot,keys,state,c=self.setup_bot()
        lowered={**state,'start':c['route'][1]['pos']}
        bot.update(.52,lowered,None,.52,True);bot.update(.56,lowered,None,.56,True)
        self.assertEqual(keys,[0x58,0x28,0x58])
        bot.update(1.1,lowered,None,1.1,True)
        self.assertTrue(bot.recovery);self.assertNotIn(0x20,keys)

    def test_focus_loss_and_garbage_discard_descent(self):
        bot,keys,state,c=self.setup_bot()
        bot.update(.52,state,None,.52,False)
        self.assertEqual(bot.phase,'paused');self.assertEqual(len(keys),2)
        bot.update(.56,state,None,.56,True)
        self.assertTrue(bot.recovery);self.assertIsNone(bot.waiting)
        bot,keys,state,c=self.setup_bot()
        changed={**state,'board':[row[:] for row in state['board']]};changed['board'][16][4]='G'
        bot.update(.52,changed,None,.52,True)
        self.assertIsNone(bot.plan);self.assertEqual(len(keys),2)

if __name__=='__main__':unittest.main()
