"""A deeper search must actually reach execution. No real keys or waits."""
import unittest
from autoplay import AutoPlayer
from test_controller import scene,advice

class LeagueTimingTests(unittest.TestCase):
    def setup_bot(self,y=-2):
        keys=[];bot=AutoPlayer(lambda k:keys.append(k) or True);bot.start(0)
        s={**scene(y=y),'tucks':True,'attackPriority':True,'profile':'versus'}
        return bot,keys,s

    def test_waits_for_construction_and_accepts_final_immediately(self):
        bot,keys,s=self.setup_bot();a=advice(s);a['stage']='fast'
        for t in (.4,.45,.6,.8):bot.update(t,s,a,t,True)
        self.assertEqual(keys,[]);self.assertEqual(bot.reason,'Planning attack sequence')
        a['stage']='final';a['candidate']['league']=True;a['candidate']['lookahead']=5
        bot.update(.81,s,a,.81,True);self.assertEqual(keys,[0x20])

    def test_bounded_fallback_does_not_restart_on_falling_frames(self):
        bot,keys,s=self.setup_bot()
        for t,y in ((.4,-2),(.6,-1),(.8,0),(.951,1)):
            s={**s,'start':dict(s['start'],y=y)};a=advice(s);a['stage']='refined'
            bot.update(t,s,a,t,True)
        self.assertEqual(keys,[0x20])

    def test_survival_or_low_clearance_does_not_wait_for_construction(self):
        for survival in (False,True):
            bot,keys,s=self.setup_bot(y=-2 if survival else 15)
            a=advice(s);a['stage']='fast';a['candidate']['lookahead']=2
            if survival:a['candidate']['auto']={'mode':'survive'}
            bot.update(.4,s,a,.4,True);bot.update(.45,s,a,.45,True)
            self.assertEqual(keys,[0x20])

if __name__=='__main__':unittest.main()
