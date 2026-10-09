import copy
import unittest
import numpy as np
import test_controller as fixtures
from test_controller import scene,advice
from overlay_vision import Reader,SHAPES
from vision_fixture import scene as pixels,blank,PALETTE

def hold_frame(piece=None,grey=False):
    frame=np.zeros((480,460,3),np.uint8)
    frame[:,140:]=pixels(blank(),'T',dict(x=3,y=-2,r=0))
    frame[80:170,8:138]=245 # white header and frame, as in the normal skin
    frame[101:165,12:134]=0
    if piece:
        for x,y in SHAPES[piece][0]:
            frame[108+y*20:127+y*20,40+x*20:59+x*20]=90 if grey else PALETTE[piece]
    return frame

class HoldTests(unittest.TestCase):
    def test_white_empty_slot_is_known_but_grey_piece_is_not_empty(self):
        for piece,grey,known in ((None,False,True),('T',False,True),('T',True,False)):
            reader=Reader()
            for _ in range(3):result=reader.read(hold_frame(piece,grey),200,400,top=80,left=140)
            self.assertEqual(result['holdKnown'],known,(piece,grey))
            if known:self.assertEqual(result['hold'],piece)

    def test_confirmed_hold_survives_unknown_and_empty_visuals_after_lock(self):
        bot,keys=fixtures.ControllerTests().bot(human=0)
        self.assertEqual(bot.resolve_hold(None,True),(None,True))
        state={**scene(),'hold':None,'allowHold':True}
        result=advice(state);result['candidate']['useHold']=True
        bot.update(.4,state,result,.4,True)
        self.assertEqual(keys,[0x10]);self.assertFalse(bot.verified_hold)
        exchanged={**state,'piece':'I','queue':['O','S','J'],'hold':'T'}
        bot.update(.44,exchanged,None,.44,True)
        self.assertEqual(bot.resolve_hold(None,False),('T',True))
        bot.hold_blocked=False;bot.held_piece=None # verified lock releases the exchange
        self.assertEqual(bot.resolve_hold(None,False),('T',True))
        self.assertEqual(bot.resolve_hold(None,True),('T',True),'a hold cannot empty itself mid-game')
        bot.recover('New capture',.6,reset=True)
        self.assertEqual(bot.resolve_hold(None,False),(None,False))

    def test_failed_hold_does_not_invent_outgoing_slot(self):
        bot,keys=fixtures.ControllerTests().bot(human=0)
        state={**scene(),'hold':'I','allowHold':True}
        result=advice(state);result['candidate']['useHold']=True
        bot.update(.4,state,result,.4,True)
        bot.update(1.2,state,result,1.2,True)
        self.assertFalse(bot.hold_verified);self.assertTrue(bot.hold_blocked)
        self.assertEqual(keys,[0x10])

if __name__=='__main__':unittest.main()
