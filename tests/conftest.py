import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

TOOLS_DIR = SCRIPTS_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
