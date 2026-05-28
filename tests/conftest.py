import os
import sys
from pathlib import Path

# Put project root on sys.path so tests can `import config`, `import logic.*` etc.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
