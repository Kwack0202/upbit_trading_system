import datetime
import random
import time
import requests
import pyupbit
import matplotlib.pyplot as plt
from PyQt5.QAxContainer import QAxWidget

from common_Import import *
from utils.Generate_plot_and_indicators import *  # plot_candles 함수를 올바르게 임포트

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
        self.volume = 3000 * 1000000
        
        # 조건2 : 24시간 등락폭 상/하한선 
        self.lower_excessive_volatility = -15.0
        self.upper_excessive_volatility = 15.0
        
        # 조건3 : 장기이평선 비교
        self.MA_length = 180
                
        # 종목 탐색 타이머        
        self.targeting_timer = 15
        '''
        ==============================================
        02. 손절/익절 기준 변수 설정 Stop loss, Take profit
        ==============================================
        '''
        self.num_SLTP = 15  # 손/익절 기준 설정을 위한 표준편차 배수값

        self.stop_loss = 0  # 손절 기준
        self.take_profit = 0  # 익절 기준

        '''
        ==============================================
        03. 포지션 진입/청산 기술적 지표 기준
        ==============================================
        '''
        self.stoch_rsi_buy = 15
        self.stoch_rsi_sell = 85
        
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
        
        '''
        ==============================================
        시스템 동작을 위한 변수
        ==============================================
        '''
        #### 거래에 활용하기 위한 변수 정의 ####       
        self.balance = 0 # 현재 계좌 정보
        self.pee = 0.00005 # 수수료
                
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
        
        try:
            self.upbit_login()
            self.get_account_info()
            self.start_trading()
        except Exception as e:
            print(f"시스템 초기화 중 오류 발생: {e}")
    
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
    def get_account_info(self):
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
           
            else:
                self.op_mode = True
                self.hold = False
                
                self.target_ticker = None
                self.target_balance = 0
                self.avg_buy_price = 0
                self.profit_rate = 0
                print("\n보유 종목 없음")
                
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
        excluded_url = "https://api.upbit.com/v1/market/all?is_details=true"
        excluded_headers = {"accept": "application/json"}
        excluded_res = requests.get(excluded_url, headers=excluded_headers)
        self.excluded_tickers += [coin['market'] for coin in excluded_res.json() if coin['market_event']['warning']]
        
        print("\n!!! Target ticker 선정을 시작합니다 !!!\n")
        print(f"조건1: 24시간 거래량 {self.volume:,}원 이상")
        print(f"조건2: 변동성 {self.lower_excessive_volatility}% 이상, {self.upper_excessive_volatility}% 이하")
        print(f"조건3: 현재 가격의 {self.MA_length} 이동 평균선 상회 여부")
        
        server_url = "https://api.upbit.com"
        params = {
            "markets": [ticker for ticker in pyupbit.get_tickers(fiat='KRW') if ticker not in self.excluded_tickers]
        }
        res = requests.get(server_url + "/v1/ticker", params=params)
        coin_info = res.json()
        

        filtered_coin_names = []
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
                    and close_price > MA_value 
                    ):
                    filtered_coin_names.append(ticker)
                    
            except Exception as e:
                    print(f"{ticker} 데이터 처리 중 오류: {e}")
                    continue        
                
            progress_bar.set_description(f'Ticker name: {ticker}')
            
        print(f"\n조건을 통과한 코인의 수: {len(filtered_coin_names)}\n")

        if filtered_coin_names:
            self.target_ticker = random.choice(filtered_coin_names)
            print(f"\nTarget ticker로 선정된 코인: {self.target_ticker}\n")
            
            self.ticker_selected_time = datetime.datetime.now()
            self.trade_occurred_since_selection = False
            print(f"\n!!!! 최종 Target ticker로 선정된 코인: {self.target_ticker} !!!!\n")
            
            self.conditions_printed = False
        else:
            print("\n조건을 만족하는 종목이 없습니다.\n")

        print("\n선정된 Target ticker로 거래를 시작합니다\n")
    
    # ======================================================================================
    def start_trading(self):
        try:
            print("\n!!! 트레이딩 시스템 시작 !!!\n")
            while True:                   
                '''
                선정된 종목에 대한 손/익절 기준을 동적으로 설정합니다
                '''
                target_ticker_df = pyupbit.get_ohlcv(self.target_ticker, f"minute{self.time_scale}", count=(self.MA_length))
                            
                trend = generate_trend(target_ticker_df)                    
                
                # 손절/익절 라인 설정 (로그 수익률 기반 평균/표준편차 사용)
                target_ticker_df['log_return'] = np.log(target_ticker_df['close'] / target_ticker_df['close'].shift(1)) * 100
                
                mean_return = target_ticker_df['log_return'].mean()
                std_return = target_ticker_df['log_return'].std()
                
                if trend == 'up':
                    self.stop_loss = mean_return - (std_return / 2) * self.num_SLTP
                    self.take_profit = abs(self.stop_loss) * 2.5
                else :
                    self.stop_loss = mean_return - (std_return / 2) * self.num_SLTP
                    self.take_profit = abs(self.stop_loss) * 2.0
                
                if not (-10.0 <= self.stop_loss <= -2.5):
                    self.stop_loss = -3.5
                    self.take_profit = abs(self.stop_loss) * 2    
                    
                """ if not self.-:
                    print(f"\n로그 수익률 평균 : {mean_return:.2f}%")
                    print(f"로그 수익률 표준편차 : {std_return:.2f}%")
                    
                    print("\n+------------------------------------------------------------+")
                    print(f"|     손절 및 익절 조건     | 손절가: {self.stop_loss:.2f}% | 익절가: {self.take_profit:.2f}% |")
                    print("+------------------------------------------------------------+")
                    
                    self.conditions_printed = True # 1회성 출력 플래그 설정 """
                
                '''
                기술적 지표 추가 및 거래 수행을 위한 현재 가격 정보를 load 합니다
                '''
                
                target_ticker_df = generate_technical_analysis_indicators(target_ticker_df)
                target_ticker_df[f'MA_{self.MA_length}'] = talib.SMA(target_ticker_df['close'], self.MA_length)

                # 현재 가격
                close = target_ticker_df.tail(1)['close'].values[0]
                
                # 볼린저 밴드 정보 
                bband_lower = target_ticker_df.tail(1)['BBAND_LOWER'].values[0]
                bband_upper = target_ticker_df.tail(1)['BBAND_UPPER'].values[0]
                
                # 스토캐스틱 RSI
                slowk_2 = target_ticker_df.tail(2)['slowk'].values[0]
                slowd_2 = target_ticker_df.tail(2)['slowd'].values[0]
                
                slowk_3 = target_ticker_df.tail(3)['slowk'].values[0]
                slowd_3 = target_ticker_df.tail(3)['slowd'].values[0]
                
                # William R%
                WR = target_ticker_df.tail(1)['WR'].values[0]
                
                # MACD
                MACD_1 = target_ticker_df.tail(1)['MACD'].values[0]
                MACD_signal_1 = target_ticker_df.tail(1)['MACD_signal'].values[0]
                
                MACD_2 = target_ticker_df.tail(2)['MACD'].values[0]
                MACD_signal_2 = target_ticker_df.tail(2)['MACD_signal'].values[0]
                
                # 장기이평선
                ma_line = target_ticker_df.tail(1)[f'MA_{self.MA_length}'].values[0]
                                    
                current_time = datetime.datetime.now()

                # Check and cancel expired orders
                orders_to_remove = []
                for order in self.active_orders:
                    time_elapsed = (current_time - order['created_at']).total_seconds()
                    if time_elapsed >= self.order_timeout:
                        try:
                            print("체결 후 일정 시간이 지난 주문에 대해 취소처리를 진행합니다")
                            self.upbit.cancel_order(uuid=order['uuid'])
                            print(f"주문 취소됨: {order['ticker']} - 가격: {order['price']:.2f}, 수량: {order['volume']:.2f}")
                            orders_to_remove.append(order)
                        except Exception as e:
                            print(f"이미 완료된 주문입니다 UUID: {order['uuid']}): {e}")
                            # If order is already executed or canceled, remove it
                            orders_to_remove.append(order)
                
                # Remove canceled or invalid orders from active_orders
                for order in orders_to_remove:
                    self.active_orders.remove(order)
                                        
                # =========================================
                # 1. No position 상태 (== 원화만 보유한 상태)
                # =========================================
                if self.target_ticker and self.op_mode ==True and self.hold == False:
                                        
                    # 계좌 정보 업데이트
                    self.balance = self.upbit.get_balances()
                    
                    # 원화 정보 조회 및 보유량 load
                    self.krw_data = [item for item in self.balance if item['currency'] == 'KRW' and float(item['balance']) >= 100]
                    self.krw_balance = int(float(self.krw_data[0]['balance'])) if self.krw_data else None
                    
                    # 거래 대상 ticker 정보 조회 및 보유량 load
                    self.target_ticker_data = [item for item in self.balance if item['currency'] != 'KRW' and float(item['avg_buy_price']) >= 0.0001 and float(item['balance']) >= 1]
                    self.target_balance = float(self.target_ticker_data[0]['balance']) if self.target_ticker_data else None
                    
                    total_invested = 0
                    
                    # 진입 비율 확인
                    for item in self.target_ticker_data:
                        currency = item['currency']
                        ticker = f"KRW-{currency}"
                        balance = float(item['balance'])
                        avg_buy_price = float(item['avg_buy_price'])
                        invested_amount = balance * avg_buy_price
                        total_invested += invested_amount
                    
                    total_capital = self.krw_balance + total_invested
                    self.seed_ratio = total_invested / total_capital
                    
                    # 거래 신호 조건
                    if (close <= bband_lower and
                        slowk_2 <= self.stoch_rsi_buy and slowd_2 <= self.stoch_rsi_buy and slowk_2 > slowd_2 and slowk_3 < slowd_3 and
                        WR <= self.WR_buy and
                        MACD_1 > MACD_signal_1 and MACD_2 < MACD_signal_2
                        ) :
                        
                        print(f"\n매수 신호 발생\n")
                        
                        print("<Technical Analysis>")
                        print(f"매수 조건 1 : 현재가격({close})이 볼린저밴드의 하단({bband_lower:.2f})을 터치")
                        print(f"매수 조건 2 : Stochastic RSI(K%의 D% 상향 돌파)")
                        print(f"매수 조건 3 : William R% 저평가 신호")
                        print(f"매수 조건 4 : MACD 골든크로스")
                        
                        # 다중 매수 주문 로직
                        investment_per_order = (self.krw_balance / self.num_orders) * (1 - self.pee) # 현재 보유 현금 / 분할 매수 주문 수
                        for i in range(self.num_orders):
                            # 가격 계산: 현재 가격에서 i * N% 하락
                            order_price = close * (1 - i * self.price_interval)
                            # 주문 수량: 투자 금액 / 주문 가격
                            order_volume = investment_per_order / order_price
                            
                            try:
                                resp = self.upbit.buy_limit_order(self.target_ticker, order_price, order_volume)
                                if 'uuid' in resp:
                                    self.active_orders.append({
                                        'uuid': resp['uuid'],
                                        'created_at': datetime.datetime.now(),
                                        'ticker': self.target_ticker,
                                        'price': order_price,
                                        'volume': order_volume
                                    })
                                    print(f"매수 주문: {self.target_ticker} - 가격: {order_price:.2f}, 수량: {order_volume:.2f}")
                                    self.trade_occurred_since_selection = True
                                    self.hold = True
                                else:
                                    print(f"매수 주문 실패")
                                    
                            except Exception as e:
                                print(f"매수 주문 중 오류 발생: {e}")
                        
                    else :
                        print(f"{current_time} | Ticker : {self.target_ticker} | Trend : {trend} | 포지션 진입 비율 {self.seed_ratio * 100:.2f}% | 손절가: {self.stop_loss:.2f}% | 익절가: {self.take_profit:.2f}% | 현재 거래 신호가 탐색되지 않았습니다")
                
                # =========================================
                # 2. position 진입 상태 (추가 매수 or 매도)
                # =========================================
                elif self.op_mode ==True and self.hold == True :
                    
                    # 계좌 정보 업데이트
                    self.balance = self.upbit.get_balances()
                    
                    # 원화 정보 조회 및 보유량 load
                    self.krw_data = [item for item in self.balance if item['currency'] == 'KRW' and float(item['balance']) >= 100]
                    self.krw_balance = int(float(self.krw_data[0]['balance'])) if self.krw_data else None
                    
                    # 거래 대상 ticker 정보 조회 및 보유량 load
                    self.target_ticker_data = [item for item in self.balance if item['currency'] != 'KRW' and float(item['avg_buy_price']) >= 0.0001 and float(item['balance']) >= 1]
                    self.target_balance = float(self.target_ticker_data[0]['balance']) if self.target_ticker_data else None
                                        
                    total_invested = 0
                                        
                    # 진입 비율 확인
                    for item in self.target_ticker_data:
                        currency = item['currency']
                        ticker = f"KRW-{currency}"
                        balance = float(item['balance'])
                        avg_buy_price = float(item['avg_buy_price'])
                        invested_amount = balance * avg_buy_price
                        total_invested += invested_amount
                    
                    total_capital = self.krw_balance + total_invested
                    self.seed_ratio = total_invested / total_capital
                                        
                    if self.target_balance:
                        self.avg_buy_price = float(self.target_ticker_data[0]['avg_buy_price'])
                        self.target_ticker_order_books = pyupbit.get_orderbook(f"{self.target_ticker}")
                        self.buy_ticker_price = self.target_ticker_order_books['orderbook_units'][0]['ask_price']
                        self.profit_rate = ((self.buy_ticker_price - self.avg_buy_price) / self.avg_buy_price) * 100
                    else:
                        self.profit_rate = None 
                    
                    # 거래 신호 조건
                    # 추가 매수
                    if (0 <= self.seed_ratio < 1.0 and 
                        close <= bband_lower and
                        slowk_2 <= self.stoch_rsi_buy and slowd_2 <= self.stoch_rsi_buy and 
                        slowk_2 > slowd_2 and slowk_3 < slowd_3 and
                        WR <= self.WR_buy and
                        MACD_1 > MACD_signal_1 and MACD_2 < MACD_signal_2 and
                        self.profit_rate <= self.stop_loss) :
                        
                        print(f"\n추가 매수 신호 발생\n")
                        
                        print("<Technical Analysis>")
                        print(f"매수 조건 1 : 현재가격({close})이 볼린저밴드의 하단({bband_lower:.2f})을 터치")
                        print(f"매수 조건 2 : Stochastic RSI(K%의 D% 상향 돌파)")
                        print(f"매수 조건 3 : William R% 저평가 신호")
                        print(f"매수 조건 4 : MACD 골든크로스")
                        
                        # 다중 매수 주문 로직
                        investment_per_order = (self.krw_balance / self.num_orders) * (1 - self.pee) # 현재 보유 현금 / 분할 매수 주문 수
                        for i in range(self.num_orders):
                            # 가격 계산: 현재 가격에서 i * N% 하락
                            order_price = close * (1 - i * self.price_interval)
                            # 주문 수량: 투자 금액 / 주문 가격
                            order_volume = investment_per_order / order_price
                            
                            try:
                                resp = self.upbit.buy_limit_order(self.target_ticker, order_price, order_volume)
                                if 'uuid' in resp:
                                    self.active_orders.append({
                                        'uuid': resp['uuid'],
                                        'created_at': datetime.datetime.now(),
                                        'ticker': self.target_ticker,
                                        'price': order_price,
                                        'volume': order_volume
                                    })
                                    print(f"매수 주문: {self.target_ticker} - 가격: {order_price:.2f}, 수량: {order_volume:.2f}")
                                    self.trade_occurred_since_selection = True
                                    self.hold = True
                                else:
                                    print(f"매수 주문 실패")
                                    
                            except Exception as e:
                                print(f"매수 주문 중 오류 발생: {e}")
                    
                    # 매도 조건 1. 익절
                    elif (0 < self.seed_ratio and
                            close >= bband_upper and
                            slowk_2 >= self.stoch_rsi_sell and slowd_2 >= self.stoch_rsi_sell and slowk_2 < slowd_2 and slowk_3 > slowd_3 and
                            WR >= self.WR_sell and
                            self.profit_rate >= self.take_profit / 2) or (self.profit_rate >= self.take_profit):
                        
                        print(f"\n매도 신호 발생\n")
                        
                        print("<Technical Analysis>")
                        print(f"매도 조건 1 : 현재가격({close})이 볼린저밴드의 상단({bband_upper:.2f})을 터치")
                        print(f"매도 조건 2 : Stochastic RSI(K%의 D% 하향 돌파)")
                        print(f"매도 조건 3 : William R% 고평가 신호")
                        print(f"매도 조건 4 : MACD 데드크로스")
                        
                        print("<Earning Rate>")
                        print(f"매도 조건 1 : 수익률({self.profit_rate:.2f}%)이 익절기준({self.take_profit}%)에 도달")
                        
                        self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                        
                        self.op_mode = False
                        self.hold = False
                        self.target_ticker = None
                        
                        # 거래 발생 플래그 설정
                        self.trade_occurred_since_selection = True                                
                    
                    # 매도 조건 2. 손절
                    elif (0.95 < self.seed_ratio and
                            self.profit_rate <= self.stop_loss) :
                        
                        print(f"\n매도 신호 발생\n")
                        
                        print("<Earning Rate>")
                        print(f"매도 조건 1 : 수익률({self.profit_rate:.2f}%)이 손절기준({self.stop_loss}%)에 도달")
                        
                        self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                        
                        self.op_mode = False
                        self.hold = False
                        self.target_ticker = None
                        
                        # 거래 발생 플래그 설정
                        self.trade_occurred_since_selection = True                                
                            
                    else :
                        print(f"{current_time} | Ticker : {self.target_ticker} | Trend : {trend} | 포지션 진입 비율 {self.seed_ratio * 100:.2f}% | 수익률 {self.profit_rate:.2f}% | 현재 거래 신호가 탐색되지 않았습니다")     

                if self.op_mode == False and self.hold == False:
                    
                    # 10초 대기 시간을 추가합니다.
                    print("매도가 진행되어 다음 거래 준비를 위해 10초 대기합니다...\n")
                    time.sleep(10)
                    
                    print("\n>>>>>계좌 정보 업데이트를 진행합니다>>>>>\n")
                    self.get_account_info()
                                        
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
                    
        except Exception as e:
            print(f"트레이딩 중 오류 발생: {e}")