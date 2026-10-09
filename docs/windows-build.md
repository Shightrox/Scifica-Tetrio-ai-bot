# Windows executable

The release is a single x64 desktop executable. It bundles Python, Tk, NumPy, Pillow, the search scripts and the official Node.js Windows runtime. There is no runtime download and neither Python nor Node needs to be on the user's PATH.

## Build

Use **64-bit Windows and Python 3.12 with Tcl/Tk**:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python scripts/build_windows.py
.venv\Scripts\python scripts/check_windows_build.py
```

The build script downloads a pinned official Node.js archive and verifies its SHA-256 against the distribution's `SHASUMS256.txt`. It creates the application icon and Windows version metadata, collects third-party license notices, then runs PyInstaller in one-file/windowed mode. Build intermediates stay in ignored `build/`; publishable files are written to ignored `dist/`:

```text
dist/
  Scifica-0.19.0-windows-x64.exe
  SHA256SUMS.txt
  BUILD-INFO.json
  LICENSE.txt
  THIRD-PARTY-LICENSES.zip
```

`check_windows_build.py` launches the actual EXE from an unrelated working directory with Python and Node removed from PATH. Its isolated local-data directory prevents changes to the user's preferences. It checks packaged vision, Tk construction, capture exclusion, a final answer from the bundled search worker, and settings that survive process exit. Autopilot remains disarmed; the test sends no game keys. This is a dependency-isolation test on the build host, not a clean-VM compatibility certification.

Build versions are recorded in `BUILD-INFO.json`. Different build hosts or dependency versions may produce different executable hashes; the recipe is repeatable, not claimed to be byte-for-byte reproducible.

## Resource paths

`app_runtime.py` resolves read-only resources relative to the bundled module. A frozen executable always uses its bundled `runtime/node.exe`, never a system Node installation. Persistent data uses `%LOCALAPPDATA%\Scifica`. Source launches continue to use the repository directory for preferences and logs.

One-file extraction and bundled resource paths follow [PyInstaller's runtime documentation](https://pyinstaller.org/en/stable/runtime-information.html). Replacing or moving the EXE does not replace saved settings.
