"""Run the shipped EXE with no Python/Node on PATH, from an unrelated directory."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app_runtime import VERSION

exe=ROOT/'dist'/f'Scifica-{VERSION}-windows-x64.exe'
with tempfile.TemporaryDirectory(prefix='Scifica isolated build ') as folder:
    folder=Path(folder);report=folder/'smoke.json'
    environment=dict(os.environ)
    windows=Path(os.environ['SYSTEMROOT'])
    environment['PATH']=str(windows/'System32')+os.pathsep+str(windows)
    environment['LOCALAPPDATA']=str(folder/'userdata')
    for key in ('PYTHONPATH','PYTHONHOME','NODE_PATH','NODE_OPTIONS'):
        environment.pop(key,None)
    result=subprocess.run([str(exe),'--smoke-test',str(report)],cwd=folder,env=environment,
                          creationflags=subprocess.CREATE_NO_WINDOW,timeout=90)
    if not report.exists():raise SystemExit(f'EXE exited {result.returncode} without a smoke-test report')
    checks=json.loads(report.read_text(encoding='utf-8'))
    print(json.dumps(checks,indent=2))
    assert result.returncode==0 and checks['ok'] and checks['frozen'] and checks['bundled_node']
    prefs=folder/'userdata'/'Scifica'/'settings.json'
    assert prefs.exists(),'Settings did not survive process exit'
    assert json.loads(prefs.read_text(encoding='utf-8'))['humanization']==23
    print('PASS isolated EXE: GUI, bundled search worker, vision, settings after exit; no game input')
