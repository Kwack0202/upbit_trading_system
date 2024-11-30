import sys
from PyQt5.QtWidgets import QApplication
from common_Import import *

class Ui_class():
    def __init__(self, version):
        self.app = QApplication(sys.argv)  # QApplication는 빈 깡통 상태의 어플 Ui
        
        if version == 'v1':
            from upbit.upbit_tradingv1 import Upbit_trading_system
        elif version == 'v2':
            from upbit.upbit_tradingv2 import Upbit_trading_system
        elif version == 'v3':
            from upbit.upbit_tradingv3 import Upbit_trading_system
        else:
            raise ValueError("지원되지 않는 버전입니다.")
        
        self.upbit = Upbit_trading_system()
        
        self.app.exec_()