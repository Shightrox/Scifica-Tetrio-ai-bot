"""Regressions reproduced in the v0.18.1 logic review. No real key input."""
import copy,unittest
from unittest.mock import patch
from autoplay import AutoPlayer,cells,locked_board
from overlay_vision import Reader,TYPES,fit_active
from test_controller import scene,advice
from vision_fixture import blank,scene as pixels

class TransitionTests(unittest.TestCase):
    def test_changed_first_legal_kick_is_replanned_before_input(self):
        keys=[];bot=AutoPlayer(lambda k:keys.append(k) or True);bot.start(0)
        s={**scene(y=6),'piece':'I'};s['board'][5][5]='J'
        result,_,end=locked_board(s['board'],'I',dict(x=4,y=5,r=1))
        bot.plan=dict(piece='I',board=s['board'],origin=dict(x=3,y=5,r=0),index=0,actions=['CW','DROP'],
                      target=cells('I',end),result=result,chain=dict(combo=0,b2b=0),
                      route=[dict(action='CW',pos=dict(x=4,y=5,r=1),kicks=[[0,0],[1,0],[-2,0],[-2,-1],[1,2]])])
        bot.update(.4,s,None,.4,True)
        self.assertEqual(keys,[]);self.assertIsNone(bot.plan);self.assertIn('Kick changed',bot.reason)

    def test_gravity_lock_releases_hold_during_or_between_inputs(self):
        for waiting in (False,True):
            bot=AutoPlayer(lambda k:True);bot.start(0);bot.hold_blocked=True;bot.chain=dict(combo=3,b2b=2)
            s=scene(y=17);bot.update(.4,s,advice(s,['L'],-1),.4,True)
            if not waiting:bot.waiting=None
            board,_,_=locked_board(s['board'],'T',s['start'])
            new={**s,'board':board,'piece':'I','start':dict(x=3,y=-2,r=0),'queue':['O','S','Z'],'generation':2}
            bot.update(.45,new,None,.45,True)
            self.assertFalse(bot.hold_blocked);self.assertEqual(bot.placed,1)
            self.assertEqual(bot.chain,dict(combo=0,b2b=2));self.assertIsNone(bot.plan)
            bot.update(.5,new,None,.5,True);self.assertEqual(bot.placed,1)

    def test_queue_tail_preserves_action_and_reverse_orientation(self):
        bot=AutoPlayer(lambda k:True);bot.start(0);s=scene()
        bot.update(.4,s,advice(s,['L'],-1),.4,True)
        moved={**s,'start':dict(s['start'],x=2),'queue':s['queue']+['J']}
        bot.update(.45,moved,None,.45,True)
        self.assertIsNotNone(bot.plan);self.assertEqual(bot.plan['index'],1)
        for piece in ('I','S','Z'):
            true=dict(x=3,y=5,r=2);raw=fit_active(cells(piece,true),TYPES.index(piece))['start']
            bot.pose=((piece,1,tuple(s['queue'])),2)
            state={**s,'piece':piece,'start':raw,'queue':moved['queue']}
            self.assertEqual(bot.resolve_pose(state,'pixels',1)['start'],true)
            state['queue']=['Z','T','O']
            self.assertTrue(bot.resolve_pose(state,'pixels',1)['start']['uncertain'])

    def test_queue_tail_or_garbage_alone_cannot_acknowledge_lock(self):
        bot=AutoPlayer(lambda k:True);bot.start(0);s=scene();bot.last_state=s;bot.hold_blocked=True
        changed=copy.deepcopy(s);changed['queue']+=['J'];changed['generation']+=1
        changed['board'][-1]=['G']*9+[None]
        bot.update(.4,changed,None,.4,True)
        self.assertTrue(bot.hold_blocked);self.assertEqual(bot.placed,0)

    def test_identical_next_queue_still_allows_verified_gravity_lock(self):
        bot=AutoPlayer(lambda k:True);bot.start(0);bot.hold_blocked=True
        before={**scene(x=4,y=18),'piece':'O','queue':['O','O','O']}
        bot.last_state=before
        board,_,_=locked_board(before['board'],'O',before['start'])
        new={**before,'board':board,'start':dict(x=4,y=-2,r=0),'generation':2}
        bot.update(.4,new,None,.4,True)
        self.assertEqual(bot.placed,1);self.assertFalse(bot.hold_blocked)

    def test_identical_hold_needs_observed_respawn(self):
        for piece in ('O','S'):
            s={**scene(x=7,y=5),'piece':piece,'hold':piece,'allowHold':True,'canHold':True}
            a=advice(s);a['candidate']['useHold']=True
            keys=[];bot=AutoPlayer(lambda k:keys.append(k) or True);bot.start(0)
            bot.update(.4,s,a,.4,True);self.assertEqual(keys,[0x10])
            bot.update(.45,s,None,.45,True);self.assertIsNotNone(bot.waiting,'ignored Shift must not be acknowledged')
            spawn={**s,'start':dict(x=4 if piece=='O' else 3,y=-2,r=0)}
            spawn=bot.resolve_pose(spawn,'pixels',.5)
            bot.update(.5,spawn,None,.5,True)
            self.assertIsNone(bot.waiting);self.assertTrue(bot.hold_blocked);self.assertEqual(bot.verified_hold,piece)

    def test_empty_hold_with_repeated_or_short_next(self):
        for queue in (['O'],['O','O','O']):
            s={**scene(x=7,y=5),'piece':'O','queue':queue,'hold':None,'allowHold':True}
            a=advice(s);a['candidate']['useHold']=True
            bot=AutoPlayer(lambda k:True);bot.start(0);bot.update(.4,s,a,.4,True)
            new={**s,'start':dict(x=4,y=-2,r=0),'queue':queue[1:]}
            bot.update(.45,new,None,.45,True)
            self.assertIsNone(bot.waiting);self.assertEqual(bot.verified_hold,'O')

    def test_repeated_dark_occlusion_never_erases_stack(self):
        board=blank();board[19][0]='L';r=Reader();pos=dict(x=3,y=-2,r=0)
        r.read(pixels(board,'T',pos),200,400,top=80)
        frame=pixels(board,'T',pos);frame[460:480,0:20]=20
        for _ in range(15):
            v=r.read(frame,200,400,top=80)
            self.assertIsNone(v['active']);self.assertGreater(v['ambiguous'],0)
            self.assertEqual(v['board'],board);self.assertEqual(r.generation,0)
        v=r.read(pixels(board,'T',pos),200,400,top=80)
        self.assertTrue(v['active']);self.assertEqual(v['ambiguous'],0)

    def test_new_round_needs_independent_reset_evidence(self):
        board=blank();board[19][0]='L';r=Reader();pos=dict(x=3,y=-2,r=0)
        r.read(pixels(board,'T',pos,['I','O','S']),200,400,top=80)
        with patch('overlay_vision.game_overlay',return_value='game-screen'):
            r.read(pixels(board,'T',pos,['I','O','S']),200,400,top=80)
        for _ in range(9):v=r.read(pixels(blank(),'J',pos,['Z','L','T']),200,400,top=80)
        self.assertEqual(v['roundId'],1);self.assertTrue(v['active']);self.assertEqual(v['board'],blank())

    def test_new_preview_tail_cannot_explain_a_disappeared_board(self):
        board=blank();board[19][0]='L';r=Reader();pos=dict(x=3,y=-2,r=0)
        r.read(pixels(board,'T',pos,['I','O','S']),200,400,top=80)
        r.hold_known=True;r.hold=None
        frame=pixels(blank(),'T',pos,['I','O','S','J'])
        for _ in range(12):v=r.read(frame,200,400,top=80)
        self.assertEqual(v['roundId'],0);self.assertIsNone(v['active']);self.assertEqual(v['board'],board)

if __name__=='__main__':unittest.main()
