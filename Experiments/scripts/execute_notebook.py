#!/usr/bin/env python3
"""Execute the descriptive notebook using this Python environment; no API calls."""
import os
from pathlib import Path
import sys
import nbformat
from nbclient import NotebookClient

experiments = Path(__file__).resolve().parents[1]
runtime = experiments / '.venv' / 'notebook-runtime'
runtime.mkdir(parents=True, exist_ok=True)
os.environ['PATH'] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', '')
os.environ['IPYTHONDIR'] = str(runtime / 'ipython')
os.environ['MPLCONFIGDIR'] = str(runtime / 'matplotlib')
os.environ['JUPYTER_RUNTIME_DIR'] = str(runtime / 'jupyter')
path = experiments / 'analysis/analyze_results.ipynb'
notebook = nbformat.read(path, as_version=4)
NotebookClient(notebook, timeout=180, kernel_name='python3',
               resources={'metadata': {'path': str(path.parent)}}).execute()
nbformat.write(notebook, path)
print(f'Executed {path.name}; outputs and plots are embedded. Provider calls: 0')
