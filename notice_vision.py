"""Find fragmented letter strokes, without OCR or notification-specific words."""
import numpy as np

def notice_mask(samples,ids):
    # Whole blocks have a consistent colour across their inner area. Glyphs
    # leave a mixture of bright strokes and background within several cells.
    counts=np.stack([(ids==i).sum(2) for i in range(1,9)],axis=2)
    dominant=counts.max(2);light=samples.max(3).astype(np.int16)
    # White lettering over an already bright coloured block can have almost
    # no brightness contrast. It still changes the other colour channels.
    contrast=(samples.max(2).astype(np.int16)-samples.min(2)).max(2)>85
    bright=(light>light.max(2)[:,:,None]-35).sum(2)
    dark=(light<light.min(2)[:,:,None]+35).sum(2)
    # White lettering on a grey notification panel shares the garbage colour
    # class. Its two brightness clusters still reveal strokes/background.
    neutral_text=(counts[:,:,7]>samples.shape[2]*.55)&(bright>=8)&(dark>=8)
    fragments=((dominant>=5)&(dominant<=samples.shape[2]*.64)|neutral_text)&contrast
    fragments[:2]=False;fragments[18:]=False
    rows=np.flatnonzero(fragments.sum(1)>=2)
    mask=np.zeros((20,10),bool)
    if not len(rows):return mask
    groups=np.split(rows,np.flatnonzero(np.diff(rows)>2)+1)
    for group in groups:
        lo,hi=int(group[0]),int(group[-1]);ys,xs=np.nonzero(fragments[lo:hi+1])
        if len(xs)<2 or hi-lo>5 or xs.max()-xs.min()<3:continue
        # Dense letters can fill the centre samples completely. Include their
        # neighbouring cells once fragmented strokes establish a text band.
        mask[max(2,lo-1):min(18,hi+2),max(0,int(xs.min())-1):min(10,int(xs.max())+2)]=True
    return mask
