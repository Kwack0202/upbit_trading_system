# __init__.py
import argparse
from ui.ui import Ui_class

class Main():
    def __init__(self, version):
        print("업비트 트레이딩 시스템을 실행합니다.\n")
        Ui_class(version)
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="업비트 트레이딩 시스템을 실행합니다.")
    parser.add_argument(
        '--version',
        choices=['v1', 'v2', 'v3'],
        default='v1',
        help='트레이딩 시스템 버전을 선택하세요: v1, v2, v3 (기본값: v1)'
    )
    args = parser.parse_args()
    Main(args.version)