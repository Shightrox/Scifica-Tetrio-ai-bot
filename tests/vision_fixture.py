import sys,json,time,subprocess,threading,queue
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from overlay_vision import Reader,SHAPES,detect,TYPES
PALETTE={'I':(70,210,180),'O':(215,196,65),'T':(180,80,195),'S':(165,220,70),'Z':(215,65,80),'J':(95,80,210),'L':(215,135,65)}
def blank():return [[None]*10 for _ in range(20)]
def scene(board,piece=None,pos=None,nexts=('I','O','J','L','T'),top=80):
 im=np.full((400+top,320,3),20,np.uint8)
 def block(x,y,t,step=20):
  x,y=round(x),round(y)
  if y>=0 and y+step<=len(im):im[y+1:y+step-1,x+1:x+step-1]=PALETTE[t]
 for y,row in enumerate(board):
  for x,t in enumerate(row):
   if t:block(x*20,top+y*20,t)
 if piece:
  for dx,dy in SHAPES[piece][pos['r']]:block((pos['x']+dx)*20,top+(pos['y']+dy)*20,piece)
 for i,t in enumerate(nexts):
  sh=SHAPES[t][0];mx=min(x for x,y in sh);my=min(y for x,y in sh)
  for x,y in sh:block(222+(x-mx)*20,top+28+i*60+(y-my)*20,t)
 return im
def read(r,b,t=None,p=None,q=('I','O','J','L','T')):return r.read(scene(b,t,p,q),200,400,top=80)
