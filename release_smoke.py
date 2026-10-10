"""Opt-in packaged-app verification; never arms autoplay or sends game keys."""
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

def run(report_path):
    app=None
    report={'ok':False,'frozen':bool(getattr(sys,'frozen',False))}
    try:
        import numpy as np
        from PIL import Image
        from overlay import Overlay
        from overlay_vision import Reader
        from app_runtime import RESOURCE_ROOT, VERSION, node_executable
        import preferences
        report['version']=VERSION
        node=node_executable()
        report['bundled_node']=Path(node).parent==RESOURCE_ROOT/'runtime'
        report['node_version']=subprocess.check_output([node,'--version'],text=True,
            creationflags=subprocess.CREATE_NO_WINDOW).strip()
        picture=Image.open(RESOURCE_ROOT/'assets/sample-board.png').convert('RGB')
        rgb=np.array(picture)[6:630,65:676]
        vision=Reader().read(rgb,260,520,top=104,left=195)
        assert vision['active']['piece']=='T',vision
        assert vision['queue'][:3]==['I','S','L'],vision
        report['vision']='T + NEXT I S L'
        app=Overlay();app.root.withdraw()
        assert not app.player.enabled
        state={'board':[[None]*10 for _ in range(20)],'piece':'T',
               'start':{'x':3,'y':-2,'r':0},'queue':['I','O','S'],
               'simpleOnly':True,'profile':'versus'}
        key=json.dumps(state,separators=(',',':'))
        app.current_key=key;app.pending=(state,key,time.perf_counter())
        app.send_pending()
        deadline=time.perf_counter()+15
        while time.perf_counter()<deadline:
            app.root.update();time.sleep(.01)
            if app.advice and app.advice['stage']=='final':break
        assert app.advice and app.advice['stage']=='final','Bundled solver did not finish'
        report['solver_stage']=app.advice['stage']
        # The dedicated PC module must also be present inside the one-file EXE.
        board=[[None]*10 for _ in range(20)]
        for y in (18,19):board[y][:2]=['O','O']
        state={'board':board,'piece':'O','start':{'x':4,'y':-2,'r':0},'queue':['O','O','O'],
               'simpleOnly':True,'profile':'versus','attackPriority':True,'allowHold':False}
        key=json.dumps(state,separators=(',',':'))
        app.advice=None;app.current_key=key;app.pending=(state,key,time.perf_counter());app.send_pending()
        deadline=time.perf_counter()+15
        while time.perf_counter()<deadline:
            app.root.update();time.sleep(.01)
            if app.advice and app.advice['stage']=='final':break
        assert app.advice and app.advice['candidate'].get('pcVerified'),'Bundled PC search failed'
        report['perfect_clear_pieces']=app.advice['candidate']['pcPieces']
        assert report['perfect_clear_pieces']==4
        board=[[None]*10 for _ in range(20)];board[17][3]='J'
        board[18]=[None if v=='.' else 'J' for v in 'XXX...XXXX']
        board[19]=[None if v=='.' else 'J' for v in 'XXXX.XXXXX']
        state={'board':board,'piece':'T','start':{'x':3,'y':-2,'r':0},'queue':['I','O','S'],
               'simpleOnly':True,'tucks':True,'rotationSystem':'srs+','allow180':True,'profile':'versus','attackPriority':True,'allowHold':False}
        key=json.dumps(state,separators=(',',':'))
        app.advice=None;app.current_key=key;app.pending=(state,key,time.perf_counter());app.send_pending()
        deadline=time.perf_counter()+15
        while time.perf_counter()<deadline:
            app.root.update();time.sleep(.01)
            if app.advice and app.advice['stage']=='final':break
        assert app.advice and app.advice['candidate'].get('spin')=='full','Bundled native spin search failed'
        assert app.advice['candidate']['requiresSoftDrop'] and app.advice['candidate']['lines']==2
        report['native_t_spin']='double with verified descent checkpoints'
        construction_check="""
        const E=require('./engine.js'),L=require('./league-search.cjs'),board=E.empty();
        board[18]=[...'XXX...XXXX'].map(v=>v==='.'?null:'J');
        board[19]=[...'XXXX.XXXXX'].map(v=>v==='.'?null:'J');
        const r=L.find({board,piece:'L',start:E.entry('L',true),queue:['T','I','O','S','Z'],
          hold:null,allowHold:false,simpleOnly:true,tucks:true,rotationSystem:'srs+',allow180:true,
          profile:'versus',attackPriority:true,chain:{combo:0,b2b:0}},{maxMs:2000,maxDepth:3});
        const c=r.candidates[0];
        if(!c.league||c.lines!==0||!c.future.some(p=>p.spin==='full'&&p.lines===2))throw Error('Missing TSD construction');
        process.stdout.write('L overhang -> T-spin double');
        """
        report['league_construction']=subprocess.check_output([node,'-e',construction_check],cwd=RESOURCE_ROOT,text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,timeout=15)
        rotation_check="""
        const E=require('./engine.js');
        for(const [piece,rows,target] of [['J',['.......X.X','..........','XXXXXXX...'],{x:7,y:18,r:0}],
          ['I',['....X...X.','...X......','.X.....X.X','...X.X....','XXXX.XXXXX'],{x:2,y:16,r:1}]]){
          const board=E.empty();rows.forEach((r,i)=>board[20-rows.length+i]=[...r].map(v=>v==='X'?'G':null));
          const options=E.placements(board,piece,E.entry(piece,true),true,false,true,{rotationSystem:'srs+',allow180:true});
          const c=options.find(c=>JSON.stringify(c.pos)===JSON.stringify(target));
          if(!c||c.lines!==1||!c.requiresSoftDrop||piece==='J'&&!c.path.includes('180'))throw Error('Missing rotation route: '+piece);
          let p=E.entry(piece,true);for(const a of c.path)p=E.move(board,piece,p,a,'srs+');
          if(JSON.stringify(p)!==JSON.stringify(c.pos))throw Error('Invalid rotation route: '+piece);
        }
        process.stdout.write('180 J single + SRS+ I single');
        """
        report['rotation_routes']=subprocess.check_output([node,'-e',rotation_check],cwd=RESOURCE_ROOT,text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,timeout=15)
        report['tk']=app.root.tk.call('info','patchlevel')
        report['capture_exclusion']=True # Overlay construction fails if unsupported.
        app.key_rate.set(17);app.humanization.set(23);app.dynamic_tempo.set(41);app.attack_priority.set(False)
        assert app.rotation_180.get()=='A' and app.player.vk['180']==0x41
        app.rotation_180.set('C');app.change_rotation_key(0x43);app.save_preferences()
        stored=preferences.load(app.data_dir/'settings.json')
        assert stored['key_rate']==17 and stored['humanization']==23,stored
        assert stored['attack_priority'] is False
        assert stored['dynamic_tempo']==41
        assert stored['rotation_180']=='C' and app.player.vk['180']==0x43
        assert not app.player.enabled
        report['persistent_data']=not app.data_dir.is_relative_to(RESOURCE_ROOT) if report['frozen'] else True
        assert report['persistent_data']
        report['ok']=True
    except Exception:
        report['error']=traceback.format_exc()
    finally:
        if app:
            try:app.close()
            except Exception:report.update(ok=False,error=traceback.format_exc())
        report_path.parent.mkdir(parents=True,exist_ok=True)
        report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return 0 if report['ok'] else 1
