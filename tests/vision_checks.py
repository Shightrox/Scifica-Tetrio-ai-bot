import copy,sys,time
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from overlay_vision import Reader,SHAPES
from vision_fixture import scene,blank,PALETTE
PALETTE['G']=(110,110,110)
fontpath='arialbd.ttf'
def lettered(frame,words=('ACHIEVEMENT','UNLOCKED'),row=7,size=22,color=(245,245,245)):
    image=Image.fromarray(frame);draw=ImageDraw.Draw(image);font=ImageFont.truetype(fontpath,size)
    for i,word in enumerate(words):
        width=draw.textlength(word,font=font)
        draw.text(((200-width)/2,80+row*20+i*(size+5)),word,font=font,fill=color,stroke_width=1)
    return np.array(image)
def read(reader,frame,action=None):return reader.read(frame,200,400,top=80,action=action)
board=blank();board[19][:7]=['L']*7
position={'x':3,'y':-2,'r':0}
for words in [('ACHIEVEMENT','UNLOCKED'),('LEVEL UP!',),('STAGE 2','COMPLETE')]:
 for size in (18,22,26):
  for color in ((245,245,245),(240,170,70),(180,100,240)):
    r=Reader();read(r,scene(board,'T',position))
    for x in (3,2,1,2):
        pos=dict(position,x=x);v=read(r,lettered(scene(board,'T',pos),words,size=size,color=color))
        assert v.get('noticeCells',0)>0,(words,size,color,v)
        assert v['board']==board and v['active']=={'piece':'T','start':pos} and v['ambiguous']==0,(words,size,color,v)
print('PASS 27 notice text/size/colour variants; visible piece keeps moving without board corruption')

for background in ((72,72,72),(95,95,95)):
 r=Reader();read(r,scene(board,'T',position))
 frame=scene(board,'T',position);frame[80+7*20:80+7*20+64,:200]=background
 v=read(r,lettered(frame));assert v['noticeCells'] and v['board']==board and v['active']['piece']=='T' and not v['ambiguous'],v
print('PASS white text on opaque grey notification panels does not become garbage')

# A DROP underneath text can be reconciled only with our sent command, shifted
# NEXT, a visible new piece, and all unobscured cells matching the result.
board=blank()
for y in range(12,20):board[y]=['G']*9+[None]
after=copy.deepcopy(board)
for x,y in SHAPES['T'][0]:after[10+y][3+x]='T'
oldq=['I','O','J','L','T'];newq=['O','J','L','T','S']
action={'action':'DROP','at':time.perf_counter(),'before_board':board,'board':after,'queue':oldq}
r=Reader();read(r,scene(board,'T',position,oldq))
frame=lettered(scene(after,'I',position,newq),('ACHIEVEMENT','UNLOCKED'),row=10)
v=read(r,frame,action)
assert v['noticeCells'] and v['board']==after and v['active']['piece']=='I' and v['ambiguous']==0,v
assert v['generation']==1
clean=read(r,scene(after,'I',position,newq));assert clean['board']==after
print('PASS predicted own DROP under a notice, NEXT acknowledgement, clean frame agrees afterwards')

bad=copy.deepcopy(after);bad[18][1]=None
r=Reader();read(r,scene(board,'T',position,oldq))
frame=lettered(scene(bad,'I',position,newq),row=10)
for _ in range(4):
    v=read(r,frame,action);assert v['ambiguous']>0 and v['active'] is None,v
assert np.count_nonzero(r.locked)==72,'contradictory visible cells must not commit forecast'
print('PASS contradictory unmasked board rejects prediction across repeated frames')

# If the piece itself is hidden, an isolated tetromino in the old stack is
# not a replacement active piece. Preserve the model but do not invent a pose.
board=blank();board[19][:7]=['L']*7
for x,y in SHAPES['O'][0]:board[12+y][6+x]='O'
r=Reader();read(r,scene(board,'T',dict(position,y=3)))
covered=scene(board,'T',dict(position,y=7));covered[80+7*20:80+10*20,:200]=20
v=read(r,lettered(covered,row=7))
assert v['noticeCells'] and v['active'] is None and v['board']==board,v
print('PASS fully hidden active piece cannot be replaced by an old stack component')

# Real grey garbage is solid, not fragmented text.
r=Reader();read(r,scene(blank(),'T',position,oldq))
garbage=blank()
for y in range(8,20):garbage[y]=['G']*5+[None]+['G']*4
v=read(r,scene(garbage,'T',position,oldq))
assert not v['noticeCells'] and v['board']==garbage and v['garbage_rise']==12,v
print('PASS real aligned garbage is not masked as a notification')
