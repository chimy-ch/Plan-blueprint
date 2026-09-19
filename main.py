"""蓝图 Blueprint —— 计划与记录。启动入口：python main.py

参数：
    --tray      启动后直接最小化到系统托盘（开机自动启动时使用）
"""

import sys

from app import main

if __name__ == "__main__":
    main(start_hidden="--tray" in sys.argv[1:])
