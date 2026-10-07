"""Geometry of large player boards with neutral or colored frame skins."""
import numpy as np

def colored_boards(rgb):
    a=rgb.astype(np.int16);h,w=a.shape[:2]
    smooth=np.zeros((h,w),bool);smooth[1:-1]=np.abs(a[2:]-a[:-2]).max(2)<=6
    bright=a.max(2)>=120
    left=np.zeros((h,w),bool);right=left.copy()
    left[:,1:]=smooth[:,:-1]&bright[:,:-1]&((a[:,:-1]-a[:,1:]).max(2)>35)
    right[:,:-1]=smooth[:,1:]&bright[:,1:]&((a[:,1:]-a[:,:-1]).max(2)>35)
    def peaks(mask):
        counts=mask.sum(0);xs=np.flatnonzero(counts>h*.22);groups=[]
        for x in xs:
            if not groups or x>groups[-1][-1]+2:groups.append([])
            groups[-1].append(int(x))
        return sorted([max(g,key=lambda x:counts[x]) for g in groups],key=lambda x:counts[x],reverse=True)[:48]
    found=[]
    for x in peaks(left):
        for edge in peaks(right):
            end=edge+1;bw=end-x
            if bw<70 or bw*2>h*1.05:continue
            same=np.abs(a[:,x-1]-a[:,end]).max(1)<24
            yy=np.flatnonzero(left[:,x]&right[:,edge]&same)
            if len(yy)<bw*.9:continue
            for ys in np.split(yy,np.flatnonzero(np.diff(yy)>bw*.2)+1):
                if len(ys)<bw*.9:continue
                lo=int(ys[0])-1;hi=int(ys[-1])+1
                error=abs((hi-lo)-bw*2)/(bw*2);coverage=len(ys)/(bw*2)
                if error<.10 and coverage>.65 and lo>=0 and lo+bw*2<=h+3:
                    found.append((bw*coverage*(1-error*5),(x,lo,bw,bw*2)))
    return found

def region_changed(old,new):
    tolerance=max(4,old[2]/10*.25)
    return any(abs(a-b)>tolerance for a,b in zip(old,new))


class GeometryGuard:
    """A working calibration wins over a larger rectangle found elsewhere."""
    def __init__(self):self.pending=None

    def accept(self,result,current,last_good,now):
        region=result.get('region');at=result.get('at',0)
        if (not result.get('verified') or not region or now-at>1 or at>now
                or current and (now-last_good<.65 or not region_changed(current,region))):
            self.pending=None;return False
        previous=self.pending
        self.pending=result
        if not previous:return False
        same=(previous['epoch']==result['epoch'] and previous['target']==result['target']
              and previous['bounds']==result['bounds'] and not region_changed(previous['region'],region))
        if same and .12<=at-previous['at']<=1.5:
            self.pending=None;return True
        return False


def capture_bounds(region):
    x,y,w,h=region
    return (x-round(w*.75),y-round(h/5),x+round(w*1.6),y+h)


def overlaps(a,b):
    return a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]


def panel_position(region,panel,work_areas):
    """Initial placement only: never clamp a panel back into the capture area."""
    blocked=capture_bounds(region);pw=panel[2]-panel[0];ph=panel[3]-panel[1]
    if not overlaps(panel,blocked):return None
    candidates=[];gap=16
    for left,top,right,bottom in work_areas:
        if right-left<pw or bottom-top<ph:continue
        xs=(left,right-pw,blocked[0]-pw-gap,blocked[2]+gap)
        ys=(top,bottom-ph,blocked[1]-ph-gap,blocked[3]+gap,panel[1])
        for x in xs:
            for y in ys:
                rect=(x,y,x+pw,y+ph)
                if left<=x and top<=y and rect[2]<=right and rect[3]<=bottom and not overlaps(rect,blocked):
                    candidates.append((x,y))
    return min(candidates,key=lambda p:(p[0]-panel[0])**2+(p[1]-panel[1])**2) if candidates else None
