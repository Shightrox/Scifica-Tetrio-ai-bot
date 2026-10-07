"""Generate the original, synthetic field used by Image lab and documentation."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from overlay_vision import SHAPES
PALETTE={'I':'#46d2b4','O':'#d7c441','T':'#b450c3','S':'#a5dc46','Z':'#d74150','J':'#5f50d2','L':'#d78741'}
image=Image.new('RGB',(840,700),'#0c1119');d=ImageDraw.Draw(image)
try: font=ImageFont.truetype('consola.ttf',18)
except OSError: font=ImageFont.load_default(size=18)
d.text((26,24),'SCIFICA / SYNTHETIC FIELD',font=font,fill='#8598af')
x0,y0,step=260,110,26
d.rectangle((x0-2,y0,x0+260+2,y0+520+2),fill='#0c1119',outline='#e1eaf5',width=2)
for x in range(1,10):d.line((x0+x*step,y0,x0+x*step,y0+520),fill='#263242')
for y in range(1,20):d.line((x0,y0+y*step,x0+260,y0+y*step),fill='#263242')
def block(x,y,p):
    d.rectangle((x+1,y+1,x+24,y+24),fill=PALETTE[p])
    d.rectangle((x+5,y+5,x+20,y+20),outline='#ffffff',width=1)
    d.rectangle((x+7,y+7,x+18,y+18),fill=PALETTE[p])
heights=[4,3,3,2,2,1,2,2,0,0]
for x,h in enumerate(heights):
    for y in range(20-h,20):block(x0+x*step,y0+y*step,list(PALETTE)[(x+y)%7])
for dx,dy in SHAPES['T'][0]:block(x0+(3+dx)*step,y0+(3+dy)*step,'T')
d.text((136,y0),'HOLD',font=font,fill='#e1eaf5')
for dx,dy in SHAPES['I'][0]:block(136+dx*step,y0+26+dy*step,'I')
d.text((554,y0),'NEXT',font=font,fill='#e1eaf5')
for i,p in enumerate(['I','S','L','O','J']):
    sh=SHAPES[p][0];mx=min(x for x,y in sh);my=min(y for x,y in sh)
    for x,y in sh:block(554+(x-mx)*step,y0+36+i*78+(y-my)*step,p)
d.text((260,655),'DEMO / NO GAME INPUT',font=font,fill='#72e6d0')
image.save(ROOT/'assets/sample-board.png')
