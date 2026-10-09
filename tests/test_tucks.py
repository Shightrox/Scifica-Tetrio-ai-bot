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

    def setup_bot(self):
        state={**scene(),'simpleOnly':True,'tucks':True,'profile':'versus','attackPriority':True,'allowHold':False}
        state['board'][17][3]='J'
        state['board'][18]=[None if v=='.' else 'J' for v in 'XXX...XXXX']
        state['board'][19]=[None if v=='.' else 'J' for v in 'XXXX.XXXXX']
        c=self.call(dict(op='analyze',state=state))['candidates'][0]
        keys=[];bot=AutoPlayer(lambda key:keys.append(key) or True);bot.start(0)
        bot.update(.4,state,dict(state=state,candidate=c,stage='final'),.4,True)
        self.assertEqual(keys,[0x58])
        moved={**state,'start':c['route'][0]['pos']}
        bot.update(.44,moved,None,.44,True);bot.update(.48,moved,None,.48,True)
        self.assertEqual(keys,[0x58,0x28])
        return bot,keys,moved,c

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
