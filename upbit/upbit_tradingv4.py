import datetime
import random
import time
import requests
import pyupbit
import matplotlib.pyplot as plt
from PyQt5.QAxContainer import QAxWidget

from common_Import import *
from utils.Generate_plot_and_indicators import *  # plot_candles 함수를 올바르게 임포트
from utils.tick_size import get_tick_size

class Upbit_trading_system(QAxWidget):
    def __init__(self):
        super().__init__()
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f'{current_time} : 업비트 OpenAPI를 사용해 계좌정보에 접근합니다.\n')
        self.upbit = None
        
        '''
        ==============================================
        00.사용자 정의 변수 지정 (수정 X)
        ==============================================
        '''
        self.target_ticker = None
            
        '''
        ==============================================
        01.종목 탐색 변수 지정
        ==============================================
        '''
        self.excluded_tickers = ['KRW-USDT'] 
        
        # Time scale
        self.time_scale = 5      
        
        # 조건1 : 24시간 거래량
        self.volume = 20000 * 1000000
        
        # 조건2 : 24시간 등락폭 상/하한선 
        self.lower_excessive_volatility = -15.0
        self.upper_excessive_volatility = 20.0
        
        # 조건3 : 장기이평선 비교
        self.MA_length = 180
        self.MA_weight = 0.99
                
        # 종목 탐색 타이머        
        self.targeting_timer = 5 * 60
        '''
        ==============================================
        02. 손절/익절 기준 변수 설정 Stop loss, Take profit
        ==============================================
        '''
        self.num_SLTP = 10  # 손/익절 기준 설정을 위한 표준편차 배수값

        self.stop_loss = 0  # 손절 기준
        self.take_profit = 0  # 익절 기준

        '''
        ==============================================
        03. 포지션 진입/청산 기술적 지표 기준
        ==============================================
        '''
        self.stoch_rsi_buy = 20
        self.stoch_rsi_sell = 80
        
        self.WR_buy = -80
        self.WR_sell = -20
        
        '''
        ==============================================
        04. 분할매수 기준 설정
        ==============================================
        '''
        self.num_orders = 4  # P: 주문 개수
        self.price_interval = 0.005  # N: 가격 간격 (0.5% = 0.005)
        self.order_timeout = 2 * 60 * 60  # 주문 유지 시간(초)
        self.active_orders = []
        
        # Reset eligible tickers
        self.eligible_tickers = []
        
        '''
        ==============================================
        시스템 동작을 위한 변수
        ==============================================
        '''
        #### 거래에 활용하기 위한 변수 정의 ####       
        self.balance = 0 # 현재 계좌 정보
        self.pee = 0.0005 # 수수료
                
        self.krw_data = 0 # 계좌 현금 정보
        self.krw_balance = 0 # 계좌 현금 보유량
        
        self.target_ticker_data = 0 # 대상 종목 정보
        self.target_balance = 0 # 대상 종목 보유량
        
        self.time_sequence = None # 시간봉 문자열
        
        self.target_ticker_order_books = 0 # 보유 종목의 호가창 정보
        
        self.op_mode = False # 시스템 실행 전 계좌정보를 불러오기 위해 잠시 시스템을 중지하는 변수
        self.hold = False # 1차 매수 이후 홀딩 변수
        self.seed_ratio = 0 # 진입한 시드의 비율을 확인
        
        self.avg_buy_price = 0 # target 종목 매수평균가
        self.buy_ticker_price = 0 # target 종목 현재가격
        self.profit_rate = 0 # target 종목 현재 수익률
            
        # 추가된 변수
        self.ticker_selected_time = None
        self.trade_occurred_since_selection = False
        self.conditions_printed = False 
        
        # 엑셀 거래 log 파일
        self.csv_file = "trading_history.csv"
        self.init_csv_file()
        
        # 거래 상태 동기화
        self.state_file = "trading_state.json"  # 상태 저장 파일
        self.load_state()
        
        try:
            self.upbit_login()
            self.update_account_info()
            self.restore_active_orders()
            self.start_trading()
        except Exception as e:
            print(f"시스템 초기화 중 오류 발생: {e}")
            
        finally:
            self.save_state()
    
    # ======================================================================================
    def save_state(self):
        """현재 상태를 JSON 파일에 저장"""
        state = {
            "target_ticker": self.target_ticker,
            "eligible_tickers": self.eligible_tickers,
            "active_orders": self.active_orders,
            "hold": self.hold,
            "op_mode": self.op_mode,
            "ticker_selected_time": self.ticker_selected_time.isoformat() if self.ticker_selected_time else None,
            "trade_occurred_since_selection": self.trade_occurred_since_selection,
            "avg_buy_price": self.avg_buy_price,
            "profit_rate": self.profit_rate,
            "target_balance": self.target_balance,
            "seed_ratio": self.seed_ratio
        }
        try:
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=4)
            # print(f"상태 저장 완료: {self.state_file}")
        except Exception as e:
            print(f"상태 저장 중 오류: {e}")
    
    # ======================================================================================
    def load_state(self):
        """저장된 상태를 복원"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                self.target_ticker = state.get("target_ticker")
                self.eligible_tickers = state.get("eligible_tickers", [])
                self.active_orders = state.get("active_orders", [])
                self.hold = state.get("hold", False)
                self.op_mode = state.get("op_mode", False)
                self.ticker_selected_time = (
                    datetime.datetime.fromisoformat(state["ticker_selected_time"])
                    if state.get("ticker_selected_time")
                    else None
                )
                self.trade_occurred_since_selection = state.get("trade_occurred_since_selection", False)
                self.avg_buy_price = state.get("avg_buy_price", 0)
                self.profit_rate = state.get("profit_rate", 0)
                self.target_balance = state.get("target_balance", 0)
                self.seed_ratio = state.get("seed_ratio", 0)
                print(f"상태 복원 완료: {self.state_file}")
            except Exception as e:
                print(f"상태 복원 중 오류: {e}")
        else:
            print(f"상태 파일이 없습니다: {self.state_file}")
    
    # ======================================================================================
    def restore_active_orders(self):
        """미체결 주문을 Upbit API로 조회하여 복원"""
        try:
            if self.target_ticker:
                orders = self.upbit.get_order(self.target_ticker, state="wait")  # 미체결 주문 조회
                self.active_orders = []
                for order in orders:
                    self.active_orders.append({
                        'uuid': order['uuid'],
                        'created_at': datetime.datetime.strptime(order['created_at'], "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None),
                        'ticker': order['market'],
                        'price': float(order['price']),
                        'volume': float(order['volume'])
                    })
                print(f"미체결 주문 복원 완료: {len(self.active_orders)}건")
                
            else:
                print("미체결된 주문 내역이 존재하지 않습니다")
        except Exception as e:
            print(f"미체결 주문 복원 중 오류: {e}")  
                          
    # ======================================================================================
    def init_csv_file(self):
        """CSV 파일 초기화"""
        columns = [
            "주문 체결 시간", "주문 종류", "수익",
            "보유 현금", "투자 금액", "현재 계좌 평가 금액"
        ]
        if not os.path.exists(self.csv_file):
            df = pd.DataFrame(columns=columns)
            df.to_csv(self.csv_file, index=False, encoding='utf-8-sig')
            print(f"CSV 파일 생성: {self.csv_file}")

    # ======================================================================================
    def save_trade_to_csv(self, order_time, order_type, profit, krw_balance, invested_amount, total_capital):
        """체결된 거래를 CSV에 저장"""
        try:
            df = pd.read_csv(self.csv_file, encoding='utf-8-sig') if os.path.exists(self.csv_file) else pd.DataFrame()
            new_row = {
                "주문 체결 시간": order_time.strftime("%Y-%m-%d %H:%M:%S"),
                "주문 종류": order_type,
                "수익": profit,
                "보유 현금": krw_balance,
                "투자 금액": invested_amount,
                "현재 계좌 평가 금액": total_capital
            }
            df = df.append(new_row, ignore_index=True)
            df.to_csv(self.csv_file, index=False, encoding='utf-8-sig')
            print(f"거래 기록 저장: {order_type} at {order_time}")
        except Exception as e:
            print(f"CSV 저장 중 오류: {e}")
    
    # ======================================================================================
    def upbit_login(self):
        try:    
            with open('./upbit_login.txt') as f:
                lines = f.readlines()
            access_key = lines[0].strip()
            secret_key = lines[1].strip()
            self.upbit = pyupbit.Upbit(access_key, secret_key)
        except FileNotFoundError:
            print("upbit_login.txt 파일을 찾을 수 없습니다. 파일 경로를 확인하세요.")
        except IndexError:
            print("upbit_login.txt 파일의 형식이 잘못되었습니다. Access key와 Secret key를 올바르게 작성했는지 확인하세요.")
        except Exception as e:
            print(f"로그인 중 오류 발생: {e}")

    # ======================================================================================
    def update_account_info(self):
        """
        계좌 정보를 조회하고, 원금 규모, 진입 비율, 수익률 등을 계산합니다.
        """
        try:
            print("\n----계좌 내 잔고 정보 조회----\n")
            self.balance = self.upbit.get_balances()

            # 원화 정보 조회
            self.krw_data = [item for item in self.balance if item['currency'] == 'KRW' and float(item['balance']) >= 100]
            self.krw_balance = int(float(self.krw_data[0]['balance'])) if self.krw_data else 0
            print(f"현금 잔고(KRW): {self.krw_balance:,} 원")

            # 보유 종목 정보 조회
            self.target_ticker_data = [
                item for item in self.balance
                if item['currency'] != 'KRW' and float(item['avg_buy_price']) >= 0.0001 and float(item['balance']) >= 1
            ]
            
            # 원금 계산 및 진입 비율 계산
            total_invested = 0
            holding_details = []

            if self.target_ticker_data:
                print("\n----보유 종목 정보----")
                for item in self.target_ticker_data:
                    currency = item['currency']
                    ticker = f"KRW-{currency}"
                    balance = float(item['balance'])
                    avg_buy_price = float(item['avg_buy_price'])
                    invested_amount = balance * avg_buy_price
                    total_invested += invested_amount

                    # 현재 가격 조회 및 수익률 계산
                    orderbook = pyupbit.get_orderbook(ticker)
                    current_price = orderbook['orderbook_units'][0]['ask_price']
                    profit_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100 if avg_buy_price > 0 else 0

                    holding_details.append({
                        'ticker': ticker,
                        'balance': balance,
                        'avg_buy_price': avg_buy_price,
                        'invested_amount': invested_amount,
                        'current_price': current_price,
                        'profit_rate': profit_rate
                    })

                    print(f"종목: {ticker}")
                    print(f"  보유 수량: {balance:,.2f}")
                    print(f"  평균 매수가: {avg_buy_price:,.2f} 원")
                    print(f"  매수 원가: {invested_amount:,.2f} 원")
                    print(f"  현재 가격: {current_price:,.2f} 원")
                    print(f"  수익률: {profit_rate:.2f}%")
                    
                self.op_mode = True
                self.hold = True

                # 대표 종목 설정
                self.target_ticker = max(holding_details, key=lambda x: x['invested_amount'])['ticker']
                self.target_balance = sum([item['balance'] for item in holding_details])
                self.avg_buy_price = sum([item['avg_buy_price'] * item['balance'] for item in holding_details]) / self.target_balance if self.target_balance > 0 else 0
                self.profit_rate = sum([item['profit_rate'] * item['invested_amount'] for item in holding_details]) / total_invested if total_invested > 0 else 0

                params = {"markets": [ticker for ticker in pyupbit.get_tickers(fiat='KRW') if ticker not in self.excluded_tickers]}
                res = requests.get("https://api.upbit.com/v1/ticker", params=params)
                coin_info = res.json()
                
                coin = [item for item in coin_info if item.get('market') == self.target_ticker][0]
                
                self.eligible_tickers.append({
                        'ticker': self.target_ticker,
                        'volume': coin.get('acc_trade_price_24h', 0) 
                    })
                                
            else:
                self.op_mode = True
                self.hold = False
                
                self.target_ticker = None
                self.target_balance = 0
                self.avg_buy_price = 0
                self.profit_rate = 0
                print("\n보유 종목 없음")
                
                if not self.target_ticker:
                    self.select_target_ticker()

            # 총 원금 계산
            total_capital = self.krw_balance + total_invested
            print(f"\n----총 자산 정보----")
            print(f"총 원금: {total_capital:,.2f} 원")
            print(f"현금 비율: {(self.krw_balance / total_capital * 100):.2f}%")
            print(f"진입 비율: {(total_invested / total_capital * 100) if total_capital > 0 else 0:.2f}%")
            
            self.seed_ratio = total_invested / total_capital
        
        except Exception as e:
            print(f"계좌 정보 조회 중 오류 발생: {e}")
    
    # ======================================================================================        
    def select_target_ticker(self):
        '''
        유의종목은 거래 대상에서 제외합니다
        '''
            
        # Exclude warning tickers
        excluded_url = "https://api.upbit.com/v1/market/all?is_details=true"
        excluded_headers = {"accept": "application/json"}
        excluded_res = requests.get(excluded_url, headers=excluded_headers)
        self.excluded_tickers += [coin['market'] for coin in excluded_res.json() if coin['market_event']['warning']]
        
        print("\n!!! Eligible tickers 선정을 시작합니다 !!!\n")
        print(f"조건1: 24시간 거래량 {self.volume:,}원 이상")
        print(f"조건2: 변동성 {self.lower_excessive_volatility}% 이상, {self.upper_excessive_volatility}% 이하")
        print(f"조건3: 현재 가격의 {self.MA_length} 이동 평균선 상회 여부")
        
        params = {"markets": [ticker for ticker in pyupbit.get_tickers(fiat='KRW') if ticker not in self.excluded_tickers]}
        res = requests.get("https://api.upbit.com/v1/ticker", params=params)
        coin_info = res.json()

        filtered_coin_info = []
        progress_bar = tqdm(coin_info)
        for coin in progress_bar:
            ticker = coin['market']
            try:
                df = pyupbit.get_ohlcv(ticker, interval=f"minute{self.time_scale}", count=self.MA_length)
                if df is None or len(df) < self.MA_length:
                    continue
                else:
                    df[f'MA_{self.MA_length}'] = talib.SMA(df['close'], self.MA_length)

                # 24시간 거래량
                acc_trade_price_24h = coin.get('acc_trade_price_24h', 0) 
                
                # 변동성 등락률
                lowest_low = df['low'].min()
                highest_high = df['high'].max()
                close_change_rate = ((highest_high - lowest_low) / lowest_low) * 100 if lowest_low > 0 else 0 
                
                # 장기이평선
                close_price = df['close'].iloc[-1]        
                MA_value = df[f'MA_{self.MA_length}'].iloc[-1]

                # 조건 체크
                if (acc_trade_price_24h >= self.volume 
                    and close_change_rate <= self.upper_excessive_volatility 
                    and close_change_rate >= self.lower_excessive_volatility 
                    and close_price > MA_value * self.MA_weight
                    ):
                    filtered_coin_info.append({
                        'ticker': ticker,
                        'volume': acc_trade_price_24h
                    })
                    
            except Exception as e:
                print(f"{ticker} 데이터 처리 중 오류: {e}")
                continue        
                
            progress_bar.set_description(f'Ticker name: {ticker}')
            
        print(f"\n조건을 통과한 코인의 수: {len(filtered_coin_info)}\n")

        if filtered_coin_info:
            self.eligible_tickers = filtered_coin_info
            # print(f"\nEligible tickers: {[item['ticker'] for item in self.eligible_tickers]}\n")
            self.ticker_selected_time = datetime.datetime.now()
            self.trade_occurred_since_selection = False
            self.conditions_printed = False
        else:
            print("\n조건을 만족하는 종목이 없습니다.\n")
            self.eligible_tickers = []
            self.target_ticker = None
    
    # ======================================================================================
    def check_order_execution(self, order):
        """주문의 체결 여부 확인"""
        try:
            order_details = self.upbit.get_order(order['uuid'])
            if order_details['state'] == 'done' and float(order_details['executed_volume']) > 0:
                executed_price = float(order_details['price'])
                executed_volume = float(order_details['executed_volume'])
                order_time = datetime.datetime.strptime(order_details['created_at'], "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
                return True, executed_price, executed_volume, order_time
            
            return False, None, None, None
        
        except Exception as e:
            print(f"주문 상태 확인 중 오류: {e}")
            return False, None, None, None        
    
    # ======================================================================================
    def manage_orders(self):
        orders_to_remove = []
        for order in self.active_orders:
            is_executed, executed_price, executed_volume, order_time = self.check_order_execution(order)
            if is_executed:
                self.update_account_info()
                self.save_trade_to_csv(
                                order_time=order_time,
                                order_type="Buy",
                                profit=0,
                                krw_balance=self.krw_balance,
                                invested_amount=self.seed_ratio * (self.krw_balance + self.seed_ratio),
                                total_capital=self.krw_balance + self.seed_ratio
                            )
                orders_to_remove.append(order)
                
            elif (datetime.datetime.now() - order['created_at']).total_seconds() >= self.order_timeout:
                try:
                    self.upbit.cancel_order(order['uuid'])
                    print(f"주문 취소: {order['ticker']} - 가격: {order['price']:.2f}, 수량: {order['volume']:.2f}")
                    orders_to_remove.append(order)
                
                except Exception as e:
                    print(f"주문 취소 오류 (UUID: {order['uuid']}): {e}")
                    orders_to_remove.append(order)
                    
        for order in orders_to_remove:
            self.active_orders.remove(order)
    
    # ======================================================================================
    def place_buy_orders(self, close):
        investment_per_order = (self.krw_balance / self.num_orders) * (1 - self.pee)
        for i in range(self.num_orders):
            # 기본 order_price 계산
            order_price = close * (1 - i * self.price_interval)
            
            # 호가 단위에 맞게 조정
            tick_size = get_tick_size(order_price)
            adjusted_order_price = (order_price // tick_size) * tick_size
            adjusted_order_price = round(adjusted_order_price, 8)  # 소수점 8자리 유지
            
            # 조정된 가격으로 주문 수량 계산
            order_volume = investment_per_order / adjusted_order_price
            try:
                resp = self.upbit.buy_limit_order(self.target_ticker, adjusted_order_price, order_volume)
                if 'uuid' in resp:
                    self.active_orders.append({
                        'uuid': resp['uuid'],
                        'created_at': datetime.datetime.now(),
                        'ticker': self.target_ticker,
                        'price': adjusted_order_price,
                        'volume': order_volume
                    })
                    print(f"매수 주문: {self.target_ticker} - 가격: {adjusted_order_price:.2f}, 수량: {order_volume:.2f}")
                    
                    # 거래 발생 플래그 설정
                    self.trade_occurred_since_selection = True
                    self.hold = True
                else:
                    print("매수 주문 실패")
            except Exception as e:
                print(f"매수 주문 오류: {e}")

        print("\n원활한 거래를 위해 매수 이후 시스템을 10초 동안 대기합니다...\n")
        time.sleep(10)
                        
    # ======================================================================================
    def place_sell_order(self):
        total_invested = self.seed_ratio * (self.krw_balance + self.seed_ratio)
        resp = self.upbit.sell_market_order(self.target_ticker, self.target_balance)
        if 'uuid' in resp:
            order_details = self.upbit.get_order(resp['uuid'])
            if order_details['state'] == 'done':
                executed_price = float(order_details['price'])
                executed_volume = float(order_details['executed_volume'])
                order_time = datetime.datetime.strptime(order_details['created_at'], "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
                profit = (executed_price - self.avg_buy_price) * executed_volume
                self.update_account_info()
                self.save_trade_to_csv(order_time, "Sell", profit, self.krw_balance, self.seed_ratio * (self.krw_balance + self.seed_ratio), self.krw_balance + self.seed_ratio)
        self.op_mode = False
        self.hold = False
        self.target_ticker = None
        
        # 거래 발생 플래그 설정
        self.trade_occurred_since_selection = True
                
    # ======================================================================================
    def start_trading(self):
        try:
            print("\n!!! 트레이딩 시스템 시작 !!!\n")
            while True:                   
                '''
                선정된 종목에 대한 손/익절 기준을 동적으로 설정합니다
                '''
                
                self.manage_orders()

                # 보유 종목이 있으면 종목 탐색 스킵
                if self.op_mode == True and self.hold == True and self.target_ticker:
                    print(f"보유 종목 감지: {self.target_ticker}. 종목 탐색을 스킵합니다.")
                else:
                    if not self.eligible_tickers:
                        print("\nEligible tickers가 없습니다. 새로운 ticker를 선정합니다.\n")
                        self.select_target_ticker()
                        time.sleep(3)
                        continue
                    
                # =========================================
                # 1. No position 상태 (== 원화만 보유한 상태)
                # =========================================
                if self.op_mode == True and self.hold == False :
                    signal_tickers = []
                    for ticker_info in self.eligible_tickers:
                        ticker = ticker_info['ticker']
                        try:
                            # Load data and calculate indicators
                            df = pyupbit.get_ohlcv(ticker, f"minute{self.time_scale}", count=self.MA_length)
                            if df is None or len(df) < self.MA_length:
                                continue

                            df = generate_technical_analysis_indicators(df)
                            df[f'MA_{self.MA_length}'] = talib.SMA(df['close'], self.MA_length)

                            # 현재 가격
                            close = df.tail(2)['close'].values[0]
                            
                            # 볼린저 밴드 정보 
                            bband_lower = df.tail(2)['BBAND_LOWER'].values[0]
                            
                            # 스토캐스틱 RSI
                            slowk_2 = df.tail(2)['slowk'].values[0]
                            slowd_2 = df.tail(2)['slowd'].values[0]
                            slowk_3 = df.tail(3)['slowk'].values[0]
                            slowd_3 = df.tail(3)['slowd'].values[0]
                            slowk_4 = df.tail(4)['slowk'].values[0]
                            slowd_4 = df.tail(4)['slowd'].values[0]
                            
                            # William R%
                            # WR = df.tail(1)['WR'].values[0]
                            
                            # MACD
                            MACD_1 = df.tail(1)['MACD'].values[0]
                            MACD_signal_1 = df.tail(1)['MACD_signal'].values[0]
                            MACD_2 = df.tail(2)['MACD'].values[0]
                            MACD_signal_2 = df.tail(2)['MACD_signal'].values[0]

                            # Check buy signal
                            if ((close <= bband_lower) and
                                (slowk_2 <= self.stoch_rsi_buy and slowd_2 <= self.stoch_rsi_buy) and 
                                ((slowk_2 > slowd_2 and slowk_3 < slowd_3) or (slowk_3 > slowd_3 and slowk_4 < slowd_4)) and
                                # WR <= self.WR_buy and
                                MACD_1 > MACD_signal_1 and MACD_2 < MACD_signal_2 ):
                                
                                signal_tickers.append(ticker_info)
                        
                        except Exception as e:
                            print(f"{ticker} 신호 확인 중 오류: {e}")
                            continue
                    
                    # =========================================
                    # 최초 거래 신호 탐색
                    # =========================================
                    if signal_tickers:
                        # If multiple signals, select the one with highest volume
                        selected_ticker_info = max(signal_tickers, key=lambda x: x['volume'])
                        self.target_ticker = selected_ticker_info['ticker']
                        
                        print(f"\n매수 신호 발생: {self.target_ticker} (거래량: {selected_ticker_info['volume']:,.2f})\n")

                        # Set stop-loss and take-profit
                        target_ticker_df = pyupbit.get_ohlcv(self.target_ticker, f"minute{self.time_scale}", count=self.MA_length)
                        trend = generate_trend(target_ticker_df)
                        target_ticker_df['log_return'] = np.log(target_ticker_df['close'] / target_ticker_df['close'].shift(1)) * 100
                        mean_return = target_ticker_df['log_return'].mean()
                        std_return = target_ticker_df['log_return'].std()
                        
                        if trend == 'up':
                            self.stop_loss = mean_return - (std_return / 2) * self.num_SLTP
                            self.take_profit = abs(self.stop_loss) * 2.5
                        
                        else:
                            self.stop_loss = mean_return - (std_return / 2) * self.num_SLTP
                            self.take_profit = abs(self.stop_loss) * 2.0
                        
                        if not (-10.0 <= self.stop_loss <= -2.5):
                            self.stop_loss = -3.5
                            self.take_profit = abs(self.stop_loss) * 2
                        
                        if not self.conditions_printed:
                            print(f"\n로그 수익률 평균 : {mean_return:.2f}%")
                            print(f"로그 수익률 표준편차 : {std_return:.2f}%")
                            
                            print("\n+------------------------------------------------------------+")
                            print(f"|     손절 및 익절 조건     | 손절가: {self.stop_loss:.2f}% | 익절가: {self.take_profit:.2f}% |")
                            print("+------------------------------------------------------------+")
                        
                            self.conditions_printed = True # 1회성 출력 플래그 설정
                    
                        self.place_buy_orders(target_ticker_df['close'].iloc[-1])
                                            
                    else:
                        print(f"{datetime.datetime.now()} | 현재 거래 신호가 탐색되지 않았습니다")
                
                # =========================================
                # 2. position 진입 상태 (추가 매수 or 매도)
                # =========================================         
                elif self.op_mode == True and self.hold == True and self.seed_ratio > 0 :
                    
                    target_ticker_df = pyupbit.get_ohlcv(self.target_ticker, f"minute{self.time_scale}", count=self.MA_length)                                  
                    target_ticker_df = generate_technical_analysis_indicators(target_ticker_df)
                    target_ticker_df[f'MA_{self.MA_length}'] = talib.SMA(target_ticker_df['close'], self.MA_length)

                    # 현재 가격
                    close = target_ticker_df.tail(2)['close'].values[0]
                    
                    # 볼린저 밴드 정보 
                    bband_lower = target_ticker_df.tail(2)['BBAND_LOWER'].values[0]
                    bband_upper = target_ticker_df.tail(2)['BBAND_UPPER'].values[0]
                    
                    # 스토캐스틱 RSI
                    slowk_2 = target_ticker_df.tail(2)['slowk'].values[0]
                    slowd_2 = target_ticker_df.tail(2)['slowd'].values[0]
                    
                    slowk_3 = target_ticker_df.tail(3)['slowk'].values[0]
                    slowd_3 = target_ticker_df.tail(3)['slowd'].values[0]
                    
                    slowk_4 = target_ticker_df.tail(4)['slowk'].values[0]
                    slowd_4 = target_ticker_df.tail(4)['slowd'].values[0]
                    
                    # William R%
                    WR = target_ticker_df.tail(1)['WR'].values[0]
                    
                    # MACD
                    MACD_1 = target_ticker_df.tail(1)['MACD'].values[0]
                    MACD_signal_1 = target_ticker_df.tail(1)['MACD_signal'].values[0]
                    
                    MACD_2 = target_ticker_df.tail(2)['MACD'].values[0]
                    MACD_signal_2 = target_ticker_df.tail(2)['MACD_signal'].values[0]
                    
                    # 장기이평선
                    ma_line = target_ticker_df.tail(1)[f'MA_{self.MA_length}'].values[0]
                    
                    if self.target_balance:
                        self.avg_buy_price = float(self.target_ticker_data[0]['avg_buy_price'])
                        self.buy_ticker_price = pyupbit.get_orderbook(self.target_ticker)['orderbook_units'][0]['ask_price']
                        self.profit_rate = ((self.buy_ticker_price - self.avg_buy_price) / self.avg_buy_price) * 100
                                                              
                    # =========================================
                    # 추가 거래 신호 탐색 (매수 or 매도 조건)
                    # =========================================
                    if (0 < self.seed_ratio < 1.0 and
                        (slowk_2 <= self.stoch_rsi_buy and slowd_2 <= self.stoch_rsi_buy) and 
                        ((slowk_2 > slowd_2 and slowk_3 < slowd_3) or (slowk_3 > slowd_3 and slowk_4 < slowd_4)) and
                        # WR <= self.WR_buy and
                        MACD_1 > MACD_signal_1 and MACD_2 < MACD_signal_2 and
                        self.profit_rate <= self.stop_loss ):
                                                
                        print(f"\n추가 매수 신호 발생\n")
                        
                        print("<Technical Analysis>")
                        print(f"매수 조건 1 : 현재가격({close})이 볼린저밴드의 하단({bband_lower:.2f})을 터치")
                        print(f"매수 조건 2 : Stochastic RSI(K%의 D% 상향 돌파)")
                        print(f"매수 조건 3 : William R% 저평가 신호")
                        print(f"매수 조건 4 : MACD 골든크로스")
                        
                        self.place_buy_orders(close)
                                            
                    # 매도 조건 1. 익절
                    elif (0 < self.seed_ratio and
                          (close >= bband_upper) and
                          (slowk_2 >= self.stoch_rsi_sell and slowd_2 >= self.stoch_rsi_sell) and 
                          (slowk_2 < slowd_2 and slowk_3 > slowd_3) and
                          # WR >= self.WR_sell and
                          self.profit_rate >= self.take_profit / 2) or (self.profit_rate >= self.take_profit):
                        
                        print(f"\n매도 신호 발생\n")
                        
                        print("<Technical Analysis>")
                        print(f"매도 조건 1 : 현재가격({close})이 볼린저밴드의 상단({bband_upper:.2f})을 터치")
                        print(f"매도 조건 2 : Stochastic RSI(K%의 D% 하향 돌파)")
                        print(f"매도 조건 3 : William R% 고평가 신호")
                        print(f"매도 조건 4 : MACD 데드크로스")
                        
                        print("<Earning Rate>")
                        print(f"매도 조건 1 : 수익률({self.profit_rate:.2f}%)이 익절기준({self.take_profit}%)에 도달")
                        
                        self.place_sell_order()                              
                    
                    # 매도 조건 2. 손절
                    elif (0.95 < self.seed_ratio and
                            self.profit_rate <= self.stop_loss) :
                        
                        print(f"\n매도 신호 발생\n")
                        
                        print("<Earning Rate>")
                        print(f"매도 조건 1 : 수익률({self.profit_rate:.2f}%)이 손절기준({self.stop_loss}%)에 도달")
                        
                        self.place_sell_order()                                
                            
                    else :
                        print(f"{datetime.datetime.now()} | Ticker : {self.target_ticker} | Trend : {trend} | 포지션 진입 비율 {self.seed_ratio * 100:.2f}% | 수익률 {self.profit_rate:.2f}% | 현재 거래 신호가 탐색되지 않았습니다")                     
                    
                if self.op_mode == False and self.hold == False:
                    
                    # 10초 대기 시간을 추가합니다.
                    print("매도가 진행되어 다음 거래 준비를 위해 10초 대기합니다...\n")
                    time.sleep(10)
                    
                    print("\n>>>>>계좌 정보 업데이트를 진행합니다>>>>>\n")
                    self.update_account_info()
                                        
                    print("거래를 시작합니다\n")
                        
                # -----------------------------------------------------------------------------------------------------------------------------------------------
                # 일정시간 동안 거래 신호가 발생하지 않았으면 새로운 코인 선택
                if self.ticker_selected_time:
                    elapsed_time = (datetime.datetime.now() - self.ticker_selected_time).total_seconds()
                    if elapsed_time > self.targeting_timer and not self.trade_occurred_since_selection:
                        print(f"\n{int(self.targeting_timer)}초 동안 거래 신호가 발생하지 않았습니다. 새로운 거래 대상 코인을 선정합니다.\n")
                        self.select_target_ticker()
                                            
                        # 추가로 포지션을 초기화할 필요가 있을 수 있습니다.
                        self.op_mode = True
                        self.hold = False

                        print("새로운 거래 대상 코인을 선정했습니다.\n")
                        
                        print("거래 준비를 위해 3초간 대기합니다...\n")
                        time.sleep(1)
                        print("3......")
                        time.sleep(1)
                        print("2....")
                        time.sleep(1)
                        print("1..!!! 거래를 시작합니다\n")
                
                self.save_state()
                    
        except Exception as e:
            print(f"트레이딩 중 오류 발생: {e}")
            self.save_state()