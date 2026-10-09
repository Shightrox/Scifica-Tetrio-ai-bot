"""Separate bundled resources from persistent user data."""
import os
from pathlib import Path
import shutil
import sys

VERSION = '0.19.1'
RESOURCE_ROOT = Path(__file__).resolve().parent

def data_directory():
    if getattr(sys, 'frozen', False):
        base = Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData'/'Local')))
        directory = base/'Scifica'
    else:
        directory = RESOURCE_ROOT
    directory.mkdir(parents=True, exist_ok=True)
    return directory

def node_executable():
    bundled = RESOURCE_ROOT/'runtime'/'node.exe'
    if bundled.is_file():
        return str(bundled)
    if getattr(sys, 'frozen', False):
        raise RuntimeError('Bundled search runtime is missing. Download Scifica again.')
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Node.js not found. Install Node.js 22 or newer and restart Scifica.')
    return node
