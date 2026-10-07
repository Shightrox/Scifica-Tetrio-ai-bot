"""Cell-aligned appearance evidence, independent of the scenery's hue."""
import numpy as np


class SpawnEdges:
    def __init__(self, width, height, top, image_shape):
        h,w=image_shape[:2]
        offsets=[]
        for side in range(4):
            for extent in (.38,.53):
                for a in np.linspace(-.3,.3,5):
                    offsets.append(((a,-extent),(extent,a),(a,extent),(-extent,a))[side])
        xx=np.array([[(x+.5+dx)*width/10 for dx,dy in offsets] for x in range(10)]).round().astype(int)
        yy=np.array([[top+(y+.5+dy)*height/20 for dx,dy in offsets] for y in range(-4,3)]).round().astype(int)
        self.indices=(np.clip(yy[:,None,:],0,h-1),np.clip(xx[None,:,:],0,w-1))
        self.valid=((yy[:,None,:]>=0)&(yy[:,None,:]<h)&(xx[None,:,:]>=0)&(xx[None,:,:]<w)).reshape(7,10,4,2,5).all(3)
        self.edge_valid=self.valid.sum(3)>=3

    def filter(self, rgb, extended, centres, shapes, types):
        """Keep spawn cells only when a tetromino's outer contour is visible.

        A large uniformly coloured sky is not a connected-component boundary.
        Test cell-aligned contours, including shapes crossing the board edge,
        and require the four cells to share an appearance, not merely a hue.
        """
        patches=rgb[self.indices].astype(np.int16).reshape(7,10,4,2,5,3)
        diff=np.abs(patches[:,:,:,0]-patches[:,:,:,1]).max(4)
        edges=((diff>=25)&self.valid).sum(3)>=3
        candidates={}
        for name,rotations in shapes.items():
            ident=types.index(name)
            anchors=list(zip(*np.nonzero(extended[:4]==ident)))
            if not anchors:continue
            for shape in rotations:
                for ay,ax in anchors:
                    for dx,dy in shape:
                        x,y=int(ax)-dx,int(ay)-dy
                        points=frozenset((x+sx,y+sy) for sx,sy in shape)
                        if points in candidates:continue
                        if any(not (0<=xx<10 and 0<=yy<7) or extended[yy,xx]!=ident for xx,yy in points):continue
                        colours=np.array([centres[yy,xx] for xx,yy in points],dtype=np.int16)
                        if (colours.max(0)-colours.min(0)).max()>60:continue
                        hits=total=0;each=True
                        for xx,yy in points:
                            local=visible=0
                            for side,(sx,sy) in enumerate(((0,-1),(1,0),(0,1),(-1,0))):
                                if (xx+sx,yy+sy) in points:continue
                                if not self.edge_valid[yy,xx,side]:continue
                                visible+=1
                                total+=1;hit=bool(edges[yy,xx,side]);hits+=hit;local+=hit
                            each &= local>0 or not visible
                        if each and total>=4 and hits>=total*.7:candidates[points]=hits/total
        keep=np.zeros((4,10),bool)
        if candidates:
            best=max(candidates.values())
            for points,score in candidates.items():
                if score<best:continue
                for x,y in points:
                    if y<4:keep[y,x]=True
        else:
            # Retain isolated edge-supported fragments for the existing unique
            # partial-pose matcher during spawn fades; no plain sky interiors.
            keep=edges[:4].sum(2)>=3
        extended[:4][~keep]=0
        return extended


def colour_support(patches, ident, ids, template=None, fragments=False):
    """Find broad remnants of a block through glyphs, rather than a centre vote."""
    match=ids==ident
    if template is not None:
        distance=np.abs(patches.astype(np.int16)-np.asarray(template,dtype=np.int16)).max(3)
        match &= distance<=65
    # Text of the same hue may occupy one narrow stroke. Block remnants need
    # area plus support in both halves of each axis of the sampling square.
    spatial=match.reshape(24,10,7,7)
    broad=(spatial[:,:,:3,:].sum((2,3))>=2)&(spatial[:,:,4:,:].sum((2,3))>=2)
    broad &=(spatial[:,:,:,:3].sum((2,3))>=2)&(spatial[:,:,:,4:].sum((2,3))>=2)
    strong=(match.sum(2)>=12)&broad
    if not fragments:return strong
    # Smaller calibrated remnants can distinguish two otherwise valid poses,
    # but may never establish a pose without two independently broad cells.
    weak=(match.sum(2)>=5)&(spatial.any(3).sum(2)>=2)&(spatial.any(2).sum(2)>=2) if template is not None else strong
    return strong,weak
