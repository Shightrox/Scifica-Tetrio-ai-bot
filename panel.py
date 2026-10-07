"""Compact Tk control surface; gameplay and capture remain in Overlay."""
import tkinter as tk
import preferences

BG = '#0c1119'
PANEL = '#131c29'
LINE = '#29394b'
FG = '#e1eaf5'
MUTED = '#8598af'
ACCENT = '#72e6d0'
AMBER = '#ffce80'
FONT = 'Consolas'

class PixelSlider(tk.Canvas):
    """Visible square thumb, mouse drag, Tab focus and arrow-key adjustment."""
    def __init__(self, parent, variable, low, high, command):
        super().__init__(parent,bg=BG,height=26,highlightthickness=0,takefocus=True,cursor='hand2')
        self.variable=variable;self.low=low;self.high=high;self.command=command
        self.bind('<Configure>',lambda e:self.draw())
        for event in ('<ButtonPress-1>','<B1-Motion>'):self.bind(event,self.pointer)
        for key,delta in [('Left',-1),('Down',-1),('Right',1),('Up',1)]:
            self.bind('<'+key+'>',lambda e,d=delta:self.set_value(variable.get()+d))
        self.bind('<Home>',lambda e:self.set_value(low))
        self.bind('<End>',lambda e:self.set_value(high))
        self.bind('<FocusIn>',lambda e:self.draw());self.bind('<FocusOut>',lambda e:self.draw())
        variable.trace_add('write',lambda *args:self.draw())
    def set_value(self,value):
        self.variable.set(max(self.low,min(self.high,round(value))));self.command()
    def pointer(self,event):
        self.focus_set();self.set_value(self.low+(event.x-8)/max(1,self.winfo_width()-16)*(self.high-self.low))
    def draw(self):
        self.delete('all');width=self.winfo_width();x=8+(width-16)*(self.variable.get()-self.low)/(self.high-self.low)
        self.create_rectangle(8,11,width-8,15,fill=LINE,outline='')
        self.create_rectangle(8,11,x,15,fill=ACCENT,outline='')
        self.create_rectangle(x-5,5,x+5,21,fill=ACCENT,outline=FG if self.focus_get()==self else ACCENT)

def build(app, root_path):
    root = app.root
    saved = preferences.load(root_path/'settings.json')
    root.configure(bg=LINE, padx=1, pady=1)
    shell = tk.Frame(root, bg=BG)
    shell.pack(fill='both', expand=True)
    titlebar = tk.Frame(shell, bg=PANEL, height=38)
    titlebar.pack(fill='x'); titlebar.pack_propagate(False)
    title = tk.Label(titlebar, text='[S]  SCIFICA / TETRIO AI BOT', bg=PANEL, fg=FG, font=(FONT, 10, 'bold'))
    title.pack(side='left', padx=14)
    def begin_drag(event):
        app._drag = (event.x_root, event.y_root, root.winfo_x(), root.winfo_y())
    def drag(event):
        if hasattr(app, '_drag'):
            x,y,rx,ry=app._drag
            root.geometry(f'{rx+event.x_root-x:+d}{ry+event.y_root-y:+d}')
    for widget in (titlebar,title):
        widget.bind('<ButtonPress-1>',begin_drag)
        widget.bind('<B1-Motion>',drag)
    def button(parent, text, command, accent=False, **kwargs):
        return tk.Button(parent, text=text, command=command, font=(FONT,10,'bold'),
                         bg=ACCENT if accent else PANEL, fg=BG if accent else FG,
                         activebackground=AMBER if accent else LINE, activeforeground=BG if accent else FG,
                         relief='flat', bd=0, highlightthickness=0, cursor='hand2', padx=12, pady=9, **kwargs)
    button(titlebar,'X',app.close,width=2).pack(side='right',fill='y')
    button(titlebar,'_',root.iconify,width=2).pack(side='right',fill='y')
    body=tk.Frame(shell,bg=BG);body.pack(fill='both',expand=True,padx=20,pady=(18,12))
    wordmark=tk.Frame(body,bg=BG);wordmark.pack(fill='x')
    tk.Label(wordmark,text='SCIFICA',font=(FONT,27,'bold'),fg=FG,bg=BG).pack(side='left')
    tk.Label(wordmark,text='v0.15\nVISION / SEARCH / PLAY',justify='right',font=(FONT,8),fg=MUTED,bg=BG).pack(side='right')
    tk.Label(body,text='[] [] [] []   LOCAL TETRIO AI',font=(FONT,9),fg=ACCENT,bg=BG).pack(anchor='w',pady=(0,14))
    def section(text):
        row=tk.Frame(body,bg=BG);row.pack(fill='x',pady=(10,8))
        tk.Label(row,text=text,font=(FONT,9,'bold'),fg=MUTED,bg=BG).pack(side='left')
        tk.Frame(row,bg=LINE,height=1).pack(side='left',fill='x',expand=True,padx=(10,0))
    section('01 / CAPTURE')
    row=tk.Frame(body,bg=BG);row.pack(fill='x')
    button(row,'[+] Select field',app.select_region).pack(side='left',fill='x',expand=True,padx=(0,6))
    button(row,'[?] Auto detect',app.auto_detect).pack(side='left',fill='x',expand=True)
    app.status=tk.StringVar(value='Select the inside of the 10 x 20 grid.')
    tk.Label(body,textvariable=app.status,font=(FONT,9),fg=MUTED,bg=BG,anchor='w',justify='left',wraplength=420,height=2).pack(fill='x',pady=(6,0))
    section('02 / INPUT')
    app.key_rate=tk.DoubleVar(value=saved['key_rate'])
    app.humanization=tk.DoubleVar(value=saved['humanization'])
    app.use_hold=tk.BooleanVar(value=saved['use_hold'])
    app.swap_rotation=tk.BooleanVar(value=saved['swap_rotation'])
    app._save_job=None
    def save_settings():
        app._save_job=None
        try: preferences.save(root_path/'settings.json',values())
        except OSError: app.status.set('Settings could not be saved.')
    def values():
        return dict(key_rate=app.key_rate.get(),humanization=app.humanization.get(),
                    use_hold=app.use_hold.get(),swap_rotation=app.swap_rotation.get())
    def changed(*args):
        app.player.configure(app.key_rate.get(),app.humanization.get())
        app.player.vk.update(CW=0x5a if app.swap_rotation.get() else 0x58,CCW=0x58 if app.swap_rotation.get() else 0x5a)
        app.speed_label.set('MAX' if app.key_rate.get()>=30 else f'{app.key_rate.get():.0f} keys/s')
        app.human_label.set(f'{app.humanization.get():.0f}%')
        if app._save_job:root.after_cancel(app._save_job)
        app._save_job=root.after(300,save_settings)
    app.save_preferences=save_settings
    app.speed_label=tk.StringVar();app.human_label=tk.StringVar()
    def slider(title, variable, label, minimum, maximum, help_text):
        row=tk.Frame(body,bg=BG);row.pack(fill='x',pady=(2,0))
        tk.Label(row,text=title,font=(FONT,11,'bold'),fg=FG,bg=BG).pack(side='left')
        tk.Label(row,textvariable=label,font=(FONT,11,'bold'),fg=ACCENT,bg=BG).pack(side='right')
        PixelSlider(body,variable,minimum,maximum,changed).pack(fill='x',pady=(3,0))
        tk.Label(body,text=help_text,font=(FONT,8),fg=MUTED,bg=BG).pack(anchor='w',pady=(0,10))
    slider('Speed',app.key_rate,app.speed_label,2,30,'Key tempo. MAX follows frame feedback.')
    slider('Humanization',app.humanization,app.human_label,0,100,'Occasional sidestep + return. Low-risk positions only.')
    toggles=tk.Frame(body,bg=BG);toggles.pack(fill='x')
    for text,var in [('HOLD / Shift',app.use_hold),('Swap Z / X',app.swap_rotation)]:
        tk.Checkbutton(toggles,text=text,variable=var,command=changed,bg=BG,fg=FG,selectcolor=PANEL,
                       activebackground=BG,activeforeground=ACCENT,font=(FONT,9),bd=0,highlightthickness=0).pack(side='left',padx=(0,16))
    section('03 / PILOT')
    row=tk.Frame(body,bg=BG);row.pack(fill='x')
    app.auto_button=button(row,'[>] Start autopilot',app.toggle_autoplay,True)
    app.auto_button.pack(side='left',fill='x',expand=True,padx=(0,6))
    button(row,'Return to game',app.focus_game).pack(side='right')
    telemetry=tk.Frame(body,bg=PANEL,highlightbackground=LINE,highlightthickness=1)
    telemetry.pack(fill='x',pady=(12,4))
    for name,value,color,height in [
        ('auto_status','OFF / Autopilot disarmed',ACCENT,2),
        ('strategy_status','AUTO / Waiting for field',AMBER,1),
        ('decision_status','NEXT --   HOLD --',FG,2),
        ('metrics_status','CAPTURE --   SEARCH --',MUTED,1)]:
        var=tk.StringVar(value=value);setattr(app,name,var)
        tk.Label(telemetry,textvariable=var,fg=color,bg=PANEL,font=(FONT,9),anchor='w',justify='left',
                 wraplength=408,height=height).pack(fill='x',padx=10,pady=(4,0))
    tk.Label(body,text='Ctrl+Alt  F7 pilot  F8 field  F9 pause  F10 panel\nEsc stop   /   Z CCW   X CW   Space drop',
             fg=MUTED,bg=BG,font=(FONT,8),justify='left',anchor='w').pack(fill='x',pady=(12,0))
    changed()
