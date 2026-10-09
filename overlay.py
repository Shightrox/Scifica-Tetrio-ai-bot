"""Windows click-through Tetris coach: ROI capture -> latest frame -> overlay.

Autoplay is explicitly armed, focus guarded, and verified against every frame.
"""
from pathlib import Path
import ctypes as C
from ctypes import wintypes as W
import json
import logging
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox
from autoplay import AutoPlayer
from game_input import GameInput
from window_chrome import WindowChrome
from app_runtime import RESOURCE_ROOT, VERSION, data_directory, node_executable

from overlay_vision import Reader, SHAPES, detect
from field_geometry import GeometryGuard, capture_bounds, overlaps, panel_position
from win_capture import Capture, user, virtual_screen, monitor_work_areas, dpi_aware, hwnd, exclude, click_through, title

ROOT=RESOURCE_ROOT
BG='#0c1119'; FG='#e1eaf5'; GREEN='#72e6d0'; KEY='#010203'

def newest(q,value):
    try:q.put_nowait(value)
    except queue.Full:
        try:q.get_nowait()
        except queue.Empty:pass
        try:q.put_nowait(value)
        except queue.Full:pass

def auto_description(plan):
    if not plan:return 'AUTO / Waiting for field'
    if plan.get('pcVerified'):
        return f"PC / {plan.get('pcPieces',1)} pieces · ~{plan.get('attackPlan',0):g} attack"
    mode={'attack':'ATTACK','balance':'BALANCE','survive':'SURVIVE'}.get(plan.get('auto',{}).get('mode'),'BALANCE')
    goal={'downstack':'downstack','perfect-clear':'perfect clear','quad':'quad',
          'prepare-quad':'prepare quad','clean-stack':'clean stack',
          'combo':f"chain up to {plan.get('comboPlan',2)} clears",'t-spin':'T-spin attack'}.get(plan.get('intent'),'replan')
    if plan.get('attackPriority') and mode!='SURVIVE':
        return f"PRESSURE / {goal} · ~{plan.get('attackPlan',0):g} attack"
    return f'AUTO / {mode} · {goal}'

class Overlay:
    def __init__(self):
        dpi_aware()
        self.timer_api=C.WinDLL('winmm')
        self.timer_raised=self.timer_api.timeBeginPeriod(1)==0
        self.root=tk.Tk();self.root.title('Scifica — Tetrio AI Bot')
        self.root.withdraw()
        self.window_chrome=WindowChrome(self.root)
        icon=ROOT/'assets/scifica.ico'
        if icon.is_file():self.root.iconbitmap(str(icon))
        self.root.configure(bg=BG);self.root.resizable(False,False)
        self.root.geometry('470x760')
        self.root.attributes('-topmost',True)
        self.data_dir=data_directory()
        self.events=logging.getLogger('tetris-autoplay');self.events.setLevel(logging.INFO)
        handler=RotatingFileHandler(self.data_dir/'autoplay-events.log',maxBytes=8000000,backupCount=2,encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        event_queue=queue.Queue();self.events.addHandler(QueueHandler(event_queue))
        self.event_listener=QueueListener(event_queue,handler);self.event_listener.start()
        self.last_player_status=None
        self.stop=threading.Event();self.frames=queue.Queue(maxsize=1);self.answers=queue.Queue()
        self.geometries=queue.Queue(maxsize=1);self.game_blocked=None;self.notice_cells=0
        self.geometry_guard=GeometryGuard();self.geometry_good_at=0;self.controls_placed=False
        self.region=None;self.enabled=True;self.reading=False;self.target=None;self.target_bounds=None
        self.current_key=None;self.pending=None;self.job=None;self.serial=0;self.capture_fps=0;self.seen_at=0
        self.latencies=[];self.capture_ms=0;self.vision_ms=0;self.advice=None;self.last_draw=None;self.last_window_check=0
        self.preview=[];self.vision_source='pixels';self.detected_hold=None;self.hold_known=False;self.spawn_age_ms=None
        self.game_input=GameInput(lambda:self.target)
        self.player=AutoPlayer(self.game_input.tap,self.game_input.release,soft_drop=self.game_input.hold_down)
        self.live_state=None;self.last_image_at=0;self.ambiguity=0;self.garbage_seen=0
        self.selector=None;self.reader_epoch=0;self.control_visible=True;self.hotkeys=[];self.key_events=queue.Queue()
        node=node_executable()
        self.node=node;self.solver_generation=0;self.solver_retry_at=None;self.solver_failures=0
        self.start_solver()
        self.vx,self.vy,self.vw,self.vh=virtual_screen()
        self.layer=tk.Toplevel(self.root);self.layer.withdraw();self.layer.overrideredirect(True)
        self.layer.configure(bg=KEY);self.layer.attributes('-topmost',True);self.layer.attributes('-transparentcolor',KEY)
        self.layer.geometry(f'{self.vw}x{self.vh}+0+0')
        self.canvas=tk.Canvas(self.layer,bg=KEY,highlightthickness=0,width=self.vw,height=self.vh)
        self.canvas.pack(fill='both',expand=True)
        self.layer.update_idletasks();click_through(self.layer)
        if not exclude(self.layer):
            raise RuntimeError('Capture exclusion failed. Windows 10 2004+ or Windows 11 is required.')
        self.setup_controls()
        self.root.update_idletasks()
        # Fixed status rows keep the panel stable when live telemetry changes.
        self.root.geometry(f'470x{self.root.winfo_reqheight()}')
        self.root.deiconify()
        self.window_chrome.configure()
        self.control_handle=hwnd(self.root)
        self.old_proc=user.GetWindowLongPtrW(self.control_handle,-4)
        @C.WINFUNCTYPE(C.c_ssize_t,C.c_void_p,W.UINT,W.WPARAM,W.LPARAM)
        def window_proc(handle,message,wp,lp):
            if message==0x312:self.key_events.put(int(wp));return 0
            return user.CallWindowProcW(self.old_proc,handle,message,wp,lp)
        self.window_proc=window_proc
        user.SetWindowLongPtrW(self.control_handle,-4,C.cast(window_proc,C.c_void_p).value)
        for ident,vk in ((1,0x77),(2,0x78),(3,0x79),(4,0x76)): # Ctrl+Alt+F7..F10
            if user.RegisterHotKey(self.control_handle,ident,0x4003,vk):self.hotkeys.append(ident)
        if len(self.hotkeys)!=4:self.status.set('Some hotkeys are already in use. Use the panel.')
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        threading.Thread(target=self.capture_loop,daemon=True).start()
        threading.Thread(target=self.geometry_loop,daemon=True).start()
        self.root.after(8,self.tick)

    def setup_controls(self):
        import panel
        panel.build(self, self.data_dir)

    def hide_controls(self):
        self.control_visible=False;self.root.withdraw()

    def show_controls(self):
        self.control_visible=True;self.window_chrome.restore()

    def focus_game(self):
        if self.target and user.IsWindow(self.target):
            user.SetForegroundWindow(self.target);self.last_window_check=0

    def change_attack_priority(self):
        if self.player.enabled:self.player.recover('Attack priority changed; replanning',time.perf_counter())
        self.live_state=None;self.current_key=None;self.pending=None;self.job=None;self.advice=None;self.last_draw=None

    def place_controls(self):
        # One-time setup only. Automatic recalibration must never move the panel.
        if self.controls_placed:return
        self.controls_placed=True
        self.root.update_idletasks()
        handle=hwnd(self.root);b=W.RECT();user.GetWindowRect(handle,C.byref(b))
        pos=panel_position(self.region,(b.left,b.top,b.right,b.bottom),monitor_work_areas())
        if pos:user.SetWindowPos(handle,None,int(pos[0]),int(pos[1]),0,0,0x15) # no activation or z-order change

    def panel_overlaps_capture(self):
        if not self.control_visible or not self.root.winfo_viewable() or not self.region or user.IsIconic(self.control_handle):return False
        b=W.RECT();user.GetWindowRect(hwnd(self.root),C.byref(b))
        return overlaps((b.left,b.top,b.right,b.bottom),capture_bounds(self.region))

    def toggle_autoplay(self):
        if self.player.enabled:self.player.stop('Stopped by user');return
        if not self.region or not self.target:
            self.status.set('Select a field first.');return
        self.focus_game()
        # Geometry is checked in the background only after the current ROI fails.
        # A synchronous full-window scan here caused both UI stalls and false jumps.
        self.reader_epoch+=1;self.live_state=None;self.pending=None
        self.player.vk.update(CW=0x5a if self.swap_rotation.get() else 0x58,CCW=0x58 if self.swap_rotation.get() else 0x5a)
        self.player.start(time.perf_counter());self.current_key=None;self.advice=None
        self.enabled=True;self.focus_game()

    def change_rotation_key(self,key):
        if self.player.vk.get('180')==key:return
        self.player.vk['180']=key
        self.player.recover('Rotation binding changed; replanning',time.perf_counter())
        self.current_key=None;self.pending=None;self.advice=None

    def select_region(self):
        if self.selector:return
        self.player.stop('Selecting field')
        self.reading=False;self.layer.withdraw();self.root.withdraw()
        s=tk.Toplevel(self.root);self.selector=s;s.overrideredirect(True);s.attributes('-topmost',True)
        s.attributes('-alpha',.32);s.configure(bg='black');s.geometry(f'{self.vw}x{self.vh}+0+0')
        s.update_idletasks();user.SetWindowPos(hwnd(s),C.c_void_p(-1),self.vx,self.vy,self.vw,self.vh,0x40)
        c=tk.Canvas(s,bg='black',cursor='crosshair',highlightthickness=0);c.pack(fill='both',expand=True)
        c.create_text(self.vw//2,55,text='Select the inside of the 10 x 20 grid.  Escape cancels.',fill='white',font=('Segoe UI',22,'bold'))
        origin=[];box=[None]
        def down(e):origin[:]=[e.x,e.y]
        def motion(e):
            if not origin:return
            if box[0]:c.delete(box[0])
            box[0]=c.create_rectangle(origin[0],origin[1],e.x,e.y,outline=GREEN,width=4)
        def cancel(e=None):
            s.destroy();self.selector=None;self.show_controls()
        def up(e):
            if not origin:return
            x=min(origin[0],e.x)+self.vx;y=min(origin[1],e.y)+self.vy
            w=abs(e.x-origin[0]);h=abs(e.y-origin[1]);s.destroy();self.selector=None
            if w<70 or h<140 or abs(h/(2*w)-1)>.16:
                self.status.set('Select the inner grid. Height should be twice its width.');self.show_controls();return
            self.root.update_idletasks();self.begin((x,y,w,h))
        c.bind('<ButtonPress-1>',down);c.bind('<B1-Motion>',motion);c.bind('<ButtonRelease-1>',up)
        s.bind('<Escape>',cancel);s.focus_force()

    def auto_detect(self):
        self.player.stop('Finding field')
        self.reading=False;self.layer.withdraw();self.root.withdraw()
        def scan():
            try:
                cap=Capture()
                try:found=detect(cap.grab(self.vx,self.vy,self.vw,self.vh),verified=True)
                finally:cap.close()
                if not found:
                    self.status.set('No field found. Use Select field.');self.show_controls();return
                x,y,w,h=found;self.begin((x+self.vx,y+self.vy,w,h))
            except Exception as exc:self.status.set(str(exc));self.show_controls()
        self.root.after(180,scan)

    def begin(self,region):
        x,y,w,h=region
        target=user.WindowFromPoint(W.POINT(x+w//2,y+h//2))
        self.target=user.GetAncestor(target,2)
        bounds=W.RECT();user.GetWindowRect(self.target,C.byref(bounds))
        self.target_bounds=(bounds.left,bounds.top,bounds.right,bounds.bottom)
        self.region=tuple(map(int,region));self.reader_epoch+=1;self.enabled=True;self.reading=True
        self.geometry_good_at=0;self.geometry_guard.pending=None
        self.current_key=None;self.pending=None;self.advice=None;self.canvas.delete('all')
        self.show_controls();self.place_controls();self.focus_game();self.last_window_check=0
        self.status.set('Tracking: '+title(self.target))

    def start_solver(self):
        self.solver=subprocess.Popen([self.node,str(ROOT/'overlay-solver.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL,text=True,encoding='utf-8',bufsize=1,
                                     creationflags=subprocess.CREATE_NO_WINDOW,cwd=ROOT)
        self.solver_generation+=1;self.solver_retry_at=None
        self.last_solver_reply=time.perf_counter()
        self.solver_requests=queue.Queue(maxsize=1)
        threading.Thread(target=self.solver_input,args=(self.solver,self.solver_generation,self.solver_requests),daemon=True).start()
        threading.Thread(target=self.solver_output,args=(self.solver,self.solver_generation),daemon=True).start()

    def solver_input(self,process,generation,requests):
        # Pipe backpressure must never block Tk, capture, or key release.
        while not self.stop.is_set() and generation==self.solver_generation:
            try:message=requests.get(timeout=.1)
            except queue.Empty:continue
            try:process.stdin.write(message);process.stdin.flush()
            except (OSError,ValueError):
                if not self.stop.is_set():self.answers.put({'stage':'fatal','error':'Search input stopped.','worker':generation})
                return

    def solver_failed(self,now,reason):
        if self.solver_retry_at is not None:return
        self.solver_failures+=1;self.solver_retry_at=now+min(8,.5*2**min(4,self.solver_failures-1))
        self.current_key=None;self.pending=None;self.job=None;self.advice=None
        self.player.recover('Restarting search; route will refresh',now)
        self.status.set(reason+' Restarting automatically.')
        try:self.solver.terminate()
        except OSError:pass

    def solver_output(self,process,generation):
        try:
            for line in process.stdout:
                if self.stop.is_set():break
                try:self.answers.put(dict(json.loads(line),worker=generation))
                except json.JSONDecodeError:pass
        finally:
            try:process.stdout.close();process.stdin.close()
            except (OSError,ValueError):pass
            if not self.stop.is_set():self.answers.put({'stage':'fatal','error':'Search process exited.','worker':generation})

    def scan_target(self,cap):
        target=self.target;epoch=self.reader_epoch
        if not target or user.GetForegroundWindow()!=target or not user.IsWindow(target) or user.IsIconic(target):return None
        if self.region and (time.perf_counter()-self.geometry_good_at<.65 or self.game_blocked or self.notice_cells):return None
        b=W.RECT();user.GetWindowRect(target,C.byref(b))
        x=max(self.vx,b.left);y=max(self.vy,b.top);right=min(self.vx+self.vw,b.right);bottom=min(self.vy+self.vh,b.bottom)
        if right-x<140 or bottom-y<280:return None
        region=self.region
        preferred=(region[0]-x,region[1]-y,region[2],region[3]) if region else None
        found=detect(cap.grab(x,y,right-x,bottom-y),verified=True,preferred=preferred)
        if user.GetForegroundWindow()!=target or epoch!=self.reader_epoch:return None
        return {'target':target,'epoch':epoch,'bounds':(b.left,b.top,b.right,b.bottom),
                'at':time.perf_counter(),'verified':bool(found),
                'region':(x+found[0],y+found[1],found[2],found[3]) if found else None}

    def geometry_loop(self):
        cap=Capture();next_scan=0
        try:
            while not self.stop.wait(.15):
                if not self.enabled or self.selector:continue
                if time.perf_counter()<next_scan:continue
                try:
                    result=self.scan_target(cap)
                    if result:
                        newest(self.geometries,result);next_scan=time.perf_counter()+(.25 if result['region'] else .6)
                except (OSError,ValueError):pass
        finally:cap.close()

    def apply_geometry(self,result):
        if result['target']!=self.target or result['epoch']!=self.reader_epoch:return False
        region=result['region']
        if not self.geometry_guard.accept(result,self.region,self.geometry_good_at,time.perf_counter()):return False
        old_region=self.region
        self.player.recover('New region; verifying field',time.perf_counter(),reset=True)
        self.region=region;self.target_bounds=result['bounds'];self.reader_epoch+=1
        self.geometry_good_at=0
        self.live_state=None;self.current_key=None;self.pending=None;self.job=None;self.advice=None;self.last_draw=None
        self.game_blocked=None;self.canvas.delete('all');self.last_window_check=0
        self.status.set('New field confirmed.')
        self.events.info('geometry '+json.dumps({'previous':old_region,'region':region,'verified':True}))
        return True

    def capture_loop(self):
        cap=Capture();reader=Reader();epoch=-1;frames=0;last=time.perf_counter()
        try:
            while not self.stop.is_set():
                started=time.perf_counter();capture_epoch=self.reader_epoch;region=self.region
                if not self.reading or not self.enabled or not region:
                    self.stop.wait(.025);continue
                if epoch!=capture_epoch:reader=Reader();epoch=capture_epoch
                x,y,w,h=region;cw=min(round(w*1.6),self.vx+self.vw-x);left=min(round(w*.75),x-self.vx)
                top=min(round(h/20*4),y-self.vy)
                try:
                    rgb=cap.grab(x-left,y-top,cw+left,h+top);captured=time.perf_counter()
                    action=self.player.waiting
                    v=reader.read(rgb,w,h,top=top,left=left,action=action);finished=time.perf_counter()
                    if capture_epoch!=self.reader_epoch or region!=self.region:continue
                    frames+=1
                    if finished-last>=.5:self.capture_fps=frames/(finished-last);frames=0;last=finished
                    newest(self.frames,{'vision':v,'at':started,'capture_ms':(captured-started)*1000,
                                       'vision_ms':(finished-captured)*1000,'epoch':capture_epoch})
                except Exception as exc:newest(self.frames,{'error':str(exc),'epoch':epoch});self.stop.wait(.25)
                self.stop.wait(max(0,1/60-(time.perf_counter()-started)))
        finally:cap.close()

    def send_pending(self):
        # A deep background calculation must never block a newer position.
        if not self.pending or self.solver_retry_at is not None:return
        state,key,at=self.pending;self.pending=None;self.serial+=1
        self.job={'id':self.serial,'key':key,'at':at}
        newest(self.solver_requests,json.dumps({'id':self.serial,'state':state},separators=(',',':'))+'\n')

    def check_window(self,now):
        if now-self.last_window_check<.12:return
        self.last_window_check=now
        if not self.target or not user.IsWindow(self.target) or not user.IsWindowVisible(self.target) or user.IsIconic(self.target):
            self.reading=False;self.layer.withdraw();return
        bounds=W.RECT();user.GetWindowRect(self.target,C.byref(bounds));b=(bounds.left,bounds.top,bounds.right,bounds.bottom)
        old=self.target_bounds
        if old and ((b[2]-b[0],b[3]-b[1])!=(old[2]-old[0],old[3]-old[1])):
            self.reading=False;self.region=None;self.reader_epoch+=1;self.live_state=None;self.advice=None;self.pending=None;self.current_key=None
            self.player.recover('Window resized; finding field',now,reset=True)
            self.layer.withdraw();self.status.set('Window resized; finding the grid.');return
        if old and (b[0],b[1])!=(old[0],old[1]):
            x,y,w,h=self.region;self.region=(x+b[0]-old[0],y+b[1]-old[1],w,h);self.target_bounds=b;self.last_draw=None
        focused=user.GetForegroundWindow()==self.target
        self.reading=focused and self.enabled and not self.selector and not self.panel_overlaps_capture()
        if self.reading:
            if not self.layer.winfo_viewable():
                self.layer.deiconify();user.SetWindowPos(hwnd(self.layer),C.c_void_p(-1),self.vx,self.vy,self.vw,self.vh,0x10)
        elif self.layer.winfo_viewable():self.layer.withdraw()

    def tick(self):
        if self.stop.is_set():return
        now=time.perf_counter()
        if self.solver_retry_at is not None and now>=self.solver_retry_at:
            try:
                self.start_solver();self.current_key=None;self.pending=None
            except OSError:
                self.solver_retry_at=None;self.solver_failed(now,'Could not start search.')
        try:self.apply_geometry(self.geometries.get_nowait())
        except queue.Empty:pass
        while True:
            try:key=self.key_events.get_nowait()
            except queue.Empty:break
            if key==1:self.select_region()
            elif key==2:self.enabled=not self.enabled;self.player.stop('Paused');self.canvas.delete('all');self.last_draw=None
            elif key==3:self.show_controls()
            elif key==4:self.toggle_autoplay()
        if self.player.enabled and user.GetAsyncKeyState(0x1b)&0x8000:self.player.stop('Stopped with Escape')
        if self.region and not self.selector:self.check_window(now)
        try:
            f=self.frames.get_nowait()
            if f['epoch']==self.reader_epoch and self.reading:
                if 'error' in f:
                    self.status.set(f['error']);self.live_state=None;self.advice=None;self.pending=None;self.current_key=None
                    self.player.recover('Capture interrupted; waiting for frames',now)
                else:
                    self.capture_ms=f['capture_ms'];self.vision_ms=f['vision_ms'];v=f['vision']
                    self.preview=v['queue'];self.vision_source=v.get('source','pixels')
                    self.spawn_age_ms=v.get('spawnAgeMs')
                    self.game_blocked=v.get('blocked')
                    self.notice_cells=v.get('noticeCells',0)
                    self.detected_hold=v.get('hold');self.hold_known=v.get('holdKnown',False)
                    held,hold_known=self.player.resolve_hold(self.detected_hold,self.hold_known)
                    self.last_image_at=f['at'];self.ambiguity=v['ambiguous'];self.garbage_seen+=v.get('garbage_rise',0)
                    if v['active'] and v['ambiguous']==0 and not self.game_blocked:
                        self.seen_at=now
                        if self.vision_source in ('pixels','partial','fragments'):self.geometry_good_at=f['at']
                        state={'board':v['board'],'piece':v['active']['piece'],'start':v['active']['start'],'queue':v['queue'],'generation':v.get('generation',0),
                               'roundId':v.get('roundId',0),
                               'simpleOnly':True,'tucks':True,'rotationSystem':'srs+','allow180':bool(self.player.vk.get('180')),'profile':'versus','chain':dict(self.player.chain),'controllerRevision':self.player.revision,'attackPriority':self.attack_priority.get(),
                               'hold':held,'allowHold':self.use_hold.get() and hold_known,'canHold':not self.player.hold_blocked}
                        state=self.player.resolve_pose(state,self.vision_source,f['at'])
                        self.live_state=state
                        key=json.dumps(state,separators=(',',':'))
                        if key!=self.current_key:
                            if self.advice and any(self.advice['state'].get(k)!=state.get(k) for k in ('board','piece','generation','hold','canHold','controllerRevision')):self.advice=None
                            self.current_key=key;self.pending=(state,key,f['at'])
                    else:
                        self.live_state=None
                        if self.game_blocked or not self.notice_cells and (v.get('event') in ('transition','garbage') or now-self.seen_at>.18):
                            self.current_key=None;self.pending=None;self.advice=None;self.last_draw=None
        except queue.Empty:pass
        while True:
            try:a=self.answers.get_nowait()
            except queue.Empty:break
            if a.get('worker')!=self.solver_generation:continue
            self.last_solver_reply=now
            if a.get('stage')=='fatal':self.solver_failed(now,a['error']);continue
            if not self.job or a.get('id')!=self.job['id']:continue
            if self.job['key']==self.current_key and 'result' in a:
                candidates=a['result']['candidates']
                if candidates:
                    self.solver_failures=0
                    lag=(time.perf_counter()-self.job['at'])*1000
                    self.advice={'candidate':candidates[0],'candidates':candidates,'state':json.loads(self.current_key),'stage':a['stage'],'ms':a['ms'],'latency':lag,'cached':a.get('cache',False)}
                    self.latencies.append(lag);self.latencies=self.latencies[-120:]
                else:
                    self.advice=None
                    self.player.recover('No route; checking field and retrying',now,delay=.4)
            if a['stage']=='error':
                self.advice=None;self.player.recover('Search failed; retrying with fresh frame',now,delay=.4)
                self.status.set(a.get('error','Search error'))
            if a['stage'] in ('final','done','error'):self.job=None
        if self.job and now-self.last_solver_reply>3:self.solver_failed(now,'Search stopped responding.')
        self.send_pending()
        foreground=user.GetForegroundWindow()
        pause_reason=None
        if self.solver_retry_at is not None:pause_reason='Search restarting automatically'
        elif foreground==self.control_handle:pause_reason='Panel focused; use Return to game'
        elif foreground==self.target and self.game_blocked:pause_reason='Game message; click inside TETR.IO'
        elif foreground==self.target and self.panel_overlaps_capture():pause_reason='Move panel clear of field and NEXT'
        elif foreground==self.target and any(k not in self.game_input.down and user.GetAsyncKeyState(k)&0x8000 for k in (0x10,0x11,0x12,0x5b,0x5c)):
            pause_reason='Release Ctrl / Alt / Shift / Win'
        self.player.update(now,self.live_state,self.advice,self.last_image_at,
                           foreground==self.target,self.vision_source,self.ambiguity,pause_reason=pause_reason,spawn_age_ms=self.spawn_age_ms)
        self.update_player_status()
        if self.reading:self.draw()
        self.root.after(8,self.tick)

    def update_player_status(self):
        strategy=auto_description(self.player.plan or (self.advice['candidate'] if self.advice else None))
        if self.strategy_status.get()!=strategy:self.strategy_status.set(strategy)
        held=self.player.verified_hold if self.player.hold_verified else self.detected_hold
        lag=f"{self.advice['latency']:.0f} ms" if self.advice else 'waiting'
        origin={'pixels':'visible','partial':'partial','fragments':'fragments','next':'from NEXT'}.get(self.vision_source,'?') if self.live_state else 'unseen'
        if self.live_state and self.vision_source=='pixels' and self.live_state['start']['y']<0:origin='above grid'
        metrics=f"{self.capture_fps:.0f} FPS / {lag} / {origin}"
        if self.metrics_status.get()!=metrics:self.metrics_status.set(metrics)
        decision=f"NEXT {' '.join(self.preview) or '--'}   HOLD {held or '--'}\nCOMBO {self.player.chain['combo']}   B2B {self.player.chain['b2b']}   LOCKS {self.player.placed}"
        if self.game_blocked:decision='Game message blocks the field.\nClick inside TETR.IO to resume.'
        elif self.notice_cells and not self.live_state:decision='Not enough visible fragments.\nKeeping the last verified plan.'
        if self.decision_status.get()!=decision:self.decision_status.set(decision)
        state=(self.player.enabled,self.player.phase,self.player.reason,self.player.placed)
        if state==self.last_player_status:return
        self.last_player_status=state
        label='PAUSED' if self.player.phase=='paused' else ('REPLAN' if self.player.phase=='recover' else ('ARMED' if self.player.enabled else 'OFF'))
        self.auto_status.set(f'{label} / {self.player.reason}')
        self.auto_button.configure(text='[x] Stop autopilot' if self.player.enabled else '[>] Start autopilot',bg='#efad80' if self.player.enabled else GREEN)
        self.events.info(json.dumps({'schema':2,'version':VERSION,'at':time.perf_counter(),
                                    'enabled':state[0],'phase':state[1],'reason':state[2],'placed':state[3],
                                    'source':self.vision_source,'ambiguous':self.ambiguity,
                                    'spawn_age_ms':round(self.spawn_age_ms) if self.spawn_age_ms is not None else None,
                                    'frame_age_ms':round((time.perf_counter()-self.last_image_at)*1000) if self.last_image_at else None,
                                    'generation':self.live_state.get('generation') if self.live_state else None,
                                    'state':self.live_state,'advice':self.advice,'plan':self.player.plan,'waiting':self.player.waiting,
                                    'chain':self.player.chain,'hold_blocked':self.player.hold_blocked,
                                    'tempo':{'speed':self.player.key_rate,'dynamic':self.player.dynamic_tempo,'human':self.player.humanization}},ensure_ascii=False))

    def draw(self):
        # The large transparent canvas is changed only on advice/state changes.
        target=self.player.plan['target'] if self.player.enabled and self.player.plan and time.perf_counter()-self.seen_at<.18 else None
        stamp=(target,self.advice and (self.advice['stage'],self.advice['candidate']['piece'],self.advice['candidate']['pos']),self.region,self.player.enabled,self.player.reason,self.control_visible,int(time.perf_counter()*2))
        if stamp==self.last_draw:return
        self.last_draw=stamp;self.canvas.delete('all')
        x,y,w,h=self.region;x-=self.vx;y-=self.vy;cw=w/10;ch=h/20
        self.canvas.create_rectangle(x-2,y-2,x+w+2,y+h+2,outline='#6e9051',width=1)
        self.canvas.create_line(x,y,x,y-4*ch,x+w,y-4*ch,x+w,y,fill='#6e9051',dash=(3,5))
        if self.advice:
            a=self.advice;c=a['candidate'];s=a['state'];p=c['pos']
            # Outline only: game blocks remain visible and mouse events pass through.
            points=target or [(p['x']+dx,p['y']+dy) for dx,dy in SHAPES[c['piece']][p['r']]]
            for dx,dy in points:
                xx=x+dx*cw;yy=y+dy*ch
                self.canvas.create_rectangle(xx+3,yy+3,xx+cw-3,yy+ch-3,outline=GREEN,width=3)
                self.canvas.create_rectangle(xx+6,yy+6,xx+cw-6,yy+ch-6,outline='#edfbd5',width=1)
            path=list(c['path'])
            while path and path[-1] in ('D','SD'):path.pop()
            symbols={'L':'←','R':'→','D':'↓','SD':'↓','CW':'↻','CCW':'↺','180':'180°'};groups=[]
            for step in path:
                if groups and groups[-1][0]==step:groups[-1][1]+=1
                else:groups.append([step,1])
            route='  '.join(symbols[v]+(f'×{n}' if n>1 else '') for v,n in groups)+'  DROP'
            source=' · cached' if a.get('cached') else (' · from NEXT' if self.vision_source=='next' else '')
            label=f"{c['piece']}  {route}\n+{c['lines']} lines · depth {c['lookahead']}{source} · {a['latency']:.0f} ms"
            timing=f"{self.capture_fps:.0f} FPS · capture {self.capture_ms:.1f} · CV {self.vision_ms:.1f} · search {a['ms']:.1f} ms"
        else:
            label='Reading piece...' if self.current_key is None else 'Searching...'
            timing=f'{self.capture_fps:.0f} FPS · Ctrl+Alt+F8 — field'
        # The persistent controls already show status; don't paint a HUD over them.
        if self.control_visible:return
        # Keep both the spawn zone above the grid and NEXT unobstructed.
        bw=330;bx=x-bw-14;by=y+4*ch
        if bx<0:bx=min(self.vw-bw-4,x+w+5.7*cw)
        self.canvas.create_rectangle(bx,by,bx+bw,by+139,fill=BG,outline='#344139')
        self.canvas.create_text(bx+10,by+7,text=label,fill=GREEN,anchor='nw',font=('Segoe UI',10,'bold'))
        self.canvas.create_text(bx+10,by+51,text=timing,fill='#abbcaf',anchor='nw',font=('Segoe UI',8))
        next_text='NEXT: '+' → '.join(self.preview) if self.preview else 'NEXT unavailable; one-piece search'
        self.canvas.create_text(bx+10,by+74,text=next_text,fill=GREEN if self.preview else '#f0ae7e',anchor='nw',font=('Segoe UI',9))
        auto_text=('AUTO: '+self.player.reason) if self.player.enabled else self.player.reason+' · Ctrl+Alt+F7'
        self.canvas.create_text(bx+10,by+96,text=auto_text[:53],fill=GREEN if self.player.enabled else '#f0ae7e',anchor='nw',font=('Segoe UI',9))
        self.canvas.create_text(bx+10,by+117,text=f"Locks {self.player.placed} · combo {self.player.chain['combo']} · B2B {self.player.chain['b2b']} · garbage ↑{self.garbage_seen}",fill='#abbcaf',anchor='nw',font=('Segoe UI',8))

    def close(self):
        self.window_chrome.cancel_drag()
        if self.stop.is_set():return
        self.save_preferences()
        self.stop.set()
        self.player.stop('Closing')
        if self.timer_raised:self.timer_api.timeEndPeriod(1)
        for ident in self.hotkeys:user.UnregisterHotKey(self.control_handle,ident)
        user.SetWindowLongPtrW(self.control_handle,-4,self.old_proc)
        try:self.solver.terminate();self.solver.wait(timeout=2)
        except (OSError,subprocess.TimeoutExpired):self.solver.kill()
        self.event_listener.stop()
        for handler in self.event_listener.handlers:handler.close()
        self.root.destroy()

    def run(self):self.root.mainloop()

if __name__=='__main__':
    import sys
    if len(sys.argv)==3 and sys.argv[1]=='--smoke-test':
        from release_smoke import run
        raise SystemExit(run(Path(sys.argv[2])))
    try:Overlay().run()
    except Exception as exc:
        try:messagebox.showerror('Scifica',str(exc))
        except Exception:pass
        raise
