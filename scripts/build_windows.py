"""Build the self-contained x64 desktop executable on Windows."""
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tkinter
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app_runtime import VERSION
NODE_VERSION='24.11.1'

def build():
    if sys.platform!='win32' or platform.machine().upper() not in ('AMD64','X86_64'):
        raise SystemExit('Build on 64-bit Windows with 64-bit Python.')
    work=ROOT/'build'/'packaging';work.mkdir(parents=True,exist_ok=True)
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    name=f'node-v{NODE_VERSION}-win-x64'
    archive=work/(name+'.zip')
    base=f'https://nodejs.org/dist/v{NODE_VERSION}/'
    sums=urllib.request.urlopen(base+'SHASUMS256.txt',timeout=60).read().decode()
    expected=next(line.split()[0] for line in sums.splitlines() if line.split()[-1]==archive.name)
    cached_hash=None
    if archive.exists():
        with archive.open('rb') as stream:cached_hash=hashlib.file_digest(stream,'sha256').hexdigest()
    if cached_hash!=expected:
        urllib.request.urlretrieve(base+archive.name,archive)
    with archive.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:
            raise SystemExit('Node.js archive checksum mismatch.')
    notices=work/'licenses';notices.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as zip_file:
        (work/'node.exe').write_bytes(zip_file.read(name+'/node.exe'))
        (notices/'Node.js.txt').write_bytes(zip_file.read(name+'/LICENSE'))
    shutil.copyfile(Path(sys.base_prefix)/'LICENSE.txt',notices/'Python.txt')
    tcl_root=Path(tkinter.Tcl().eval('info library')).parent
    for path in tcl_root.glob('*/license.terms'):
        shutil.copyfile(path,notices/(path.parent.name+'.txt'))
    for package in ('numpy','Pillow','pyinstaller'):
        distribution=metadata.distribution(package)
        for entry in distribution.files or []:
            if '.dist-info/licenses/' in str(entry).replace('\\','/'):
                target=notices/package/Path(str(entry).split('licenses/',1)[-1])
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(distribution.locate_file(entry),target)
    # Original code-drawn pixel mark, matching assets/mark.svg.
    from PIL import Image,ImageDraw
    icon=Image.new('RGBA',(256,256),'#0c1119');draw=ImageDraw.Draw(icon)
    for x,y in ((28,12),(44,12),(12,28),(28,28)):
        draw.rectangle((x*4,y*4,(x+15)*4,(y+15)*4),fill='#72e6d0')
    icon.save(work/'scifica.ico',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    executable_name=f'Scifica-{VERSION}-windows-x64'
    version=tuple(map(int,VERSION.split('.')))+(0,)
    (work/'version.txt').write_text(f'''VSVersionInfo(
      ffi=FixedFileInfo(filevers={version!r},prodvers={version!r},mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),
      kids=[StringFileInfo([StringTable('040904B0',[
        StringStruct('CompanyName','Shightrox'),
        StringStruct('FileDescription','Scifica - Tetrio AI Bot'),
        StringStruct('FileVersion','{VERSION}'),StringStruct('ProductVersion','{VERSION}'),
        StringStruct('ProductName','Scifica'),
        StringStruct('OriginalFilename','{executable_name}.exe'),
        StringStruct('LegalCopyright','Copyright (c) 2026 Shightrox; MIT license')])]),
        VarFileInfo([VarStruct('Translation',[1033,1200])])])''',encoding='utf-8')
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--onefile','--windowed','--noupx',
             '--name',executable_name,'--distpath',str(dist),'--workpath',str(work/'pyinstaller'),
             '--specpath',str(work),'--icon',str(work/'scifica.ico'),'--version-file',str(work/'version.txt'),
             '--add-binary',f'{work/"node.exe"}{os.pathsep}runtime',
             '--add-data',f'{work/"scifica.ico"}{os.pathsep}assets',
             '--add-data',f'{notices}{os.pathsep}licenses']
    for path,destination in [('engine.js','.'),('overlay-solver.cjs','.'),('LICENSE','.'),('assets/sample-board.png','assets')]:
        command.extend(['--add-data',f'{ROOT/path}{os.pathsep}{destination}'])
    command.append(str(ROOT/'overlay.py'))
    subprocess.run(command,cwd=ROOT,check=True)
    exe=dist/(executable_name+'.exe')
    with exe.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    (dist/'SHA256SUMS.txt').write_text(f'{digest}  {exe.name}\n',encoding='utf-8')
    versions={name:metadata.version(name) for name in ('numpy','Pillow','pyinstaller')}
    (dist/'BUILD-INFO.json').write_text(json.dumps({'version':VERSION,'platform':'windows-x64',
        'python':platform.python_version(),'node':NODE_VERSION,'packages':versions,'sha256':digest},indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(ROOT/'LICENSE',dist/'LICENSE.txt')
    shutil.make_archive(str(dist/'THIRD-PARTY-LICENSES'),'zip',notices)
    print(f'Built {exe.name} ({exe.stat().st_size/1024/1024:.1f} MiB)',flush=True)

if __name__=='__main__':build()
