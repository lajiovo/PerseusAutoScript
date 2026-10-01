import sys
from pathlib import Path

# 获取 module 文件夹自身的路径
MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import zOnepush