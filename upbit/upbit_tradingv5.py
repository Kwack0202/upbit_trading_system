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
        self.excluded_tickers = ['KRW-USDT', 'KRW-USDC', 'KRW-BTC', "KRW-ETH"] 
        
        # Time scale 
        self.time_scale = 5 # 거래용 Time
        
        # 조건1 : 24시간 거래량
        self.volume = 5000 * 1000000
        
        # 조건2 : 변동성 등락폭 상/하한선 
        self.upper_excessive_volatility = 20 # 저점 대비 상승률 
        self.lower_excessive_volatility = -25 # 고점 대비 하락률
        
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
        self.stop_loss = 0
        self.take_profit = 0
        
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
        self.num_orders = 10  # P: 주문 개수
        self.price_interval = 0.005  # N: 가격 간격 (0.005 = 0.5%)
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
        self.c = 0.0005 # 수수료
                
        self.krw_data = 0 # 계좌 현금 정보
        self.krw_balance = 0 # 계좌 현금 보유량
        
        self.total_invested = 0 # 계좌 투자 금액
        self.total_capital = 0 # 계좌 총 가치 평가        
               
        self.target_ticker_data = 0 # 대상 종목 정보
        self.target_balance = 0 # 대상 종목 보유량
        
        self.time_sequence = None # 시간봉 문자열
        
        self.target_ticker_order_books = 0 # 보유 종목의 호가창 정보
        
        self.op_mode = False # 시스템 실행 전 계좌정보를 불러오기 위해 잠시 시스템을 중지하는 변수
        self.hold = False # 1차 매수 이후 홀딩 변수
        self.seed_ratio = 0 # 진입한 시드의 비율을 확인
        
        self.uncommitted_amount = 0 # 미체결 주문 금액
        
        self.avg_buy_price = 0 # target 종목 매수평균가
        self.buy_ticker_price = 0 # target 종목 현재가격
        self.profit_rate = 0 # target 종목 현재 수익률
            
        # 추가된 변수
        self.ticker_selected_time = None
        self.trade_occurred_since_selection = False
        self.conditions_printed = False 
                        
        try:
            self.upbit_login()
            self.update_account_info()
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

                self.restore_active_orders()

                print(f"종목: {ticker}")
                print(f"  보유 수량: {balance:,.2f}")
                print(f"  평균 매수가: {avg_buy_price:,.2f} 원")
                print(f"  매수 금액: {invested_amount:,.2f} 원")
                print(f"  미체결 주문 금액 : {self.uncommitted_amount:,.2f}원")
                print(f"  현재 가격: {current_price:,.2f} 원")
                print(f"  수익률: {profit_rate:.2f}%")
                            
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

            # 포지션 진입 금액
            self.total_invested = total_invested
            
            # 총 원금 계산
            total_capital = self.krw_balance + self.total_invested + self.uncommitted_amount
            
            print(f"\n----총 자산 정보----")
            print(f"총 원금: {total_capital:,.2f} 원")
            print(f"현금 비율: {(self.krw_balance / total_capital * 100):.2f}%")
            print(f"진입 비율: {(total_invested / total_capital * 100) if total_capital > 0 else 0:.2f}%")
            self.total_capital = total_capital
            
            # 포지션 진입 비율
            self.seed_ratio = self.total_invested / self.total_capital
        
        
        except Exception as e:
            print(f"계좌 정보 조회 중 오류 발생: {e}")
    
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
                
                self.uncommitted_amount = sum(float(item['price']) * float(item['volume']) for item in orders)
                
            else:
                print("미체결된 주문 내역이 존재하지 않습니다")
        
        except Exception as e:
            print(f"미체결 주문 복원 중 오류: {e}") 
             
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
        print(f"조건2: 가장 저점 대비 상승률 및 가장 고점 대비 하락률 기준")
        print(f"조건3: 현재 가격의 {self.MA_length} 이동 평균선 상회 여부")
        print(f"조건4: 하락 추세 제외")
        
        params = {"markets": [ticker for ticker in pyupbit.get_tickers(fiat='KRW') if ticker not in self.excluded_tickers]}
        res = requests.get("https://api.upbit.com/v1/ticker", params=params)
        coin_info = res.json()

        filtered_coin_info = []
        progress_bar = tqdm(coin_info)
        for coin in progress_bar:
            ticker = coin['market']
            try:
                short_df = pyupbit.get_ohlcv(ticker, interval=f"minute{self.time_scale}", count= self.MA_length)
                long_df = pyupbit.get_ohlcv(ticker, interval="minute60", count= 24 * 3)
                        
                if short_df is None or len(short_df) < self.MA_length:
                    continue
                else:
                    short_df[f'MA_{self.MA_length}'] = talib.SMA(short_df['close'], self.MA_length)
                
                if long_df is None or len(long_df) < (24 * 3):
                    continue
                    
                # 24시간 거래량
                acc_trade_price_24h = coin.get('acc_trade_price_24h', 0) 
                
                # Long df - 변동성 계산: 저점 대비 상승률, 고점 대비 하락률
                lowest_low = long_df['low'].min()
                highest_high = long_df['high'].max()
                close_price = long_df['close'].iloc[-1]
                
                rise_from_low = ((close_price - lowest_low) / lowest_low) * 100 if lowest_low > 0 else 0 
                fall_from_high = ((highest_high - close_price) / highest_high) * 100 if highest_high > 0 else 0 
                
                # Short df - 장기이평선    
                MA_value = short_df[f'MA_{self.MA_length}'].iloc[-1]
                
                # short df - 추세 체크
                trend = generate_trend(short_df)
                
                # 조건 체크
                if ((acc_trade_price_24h >= self.volume)
                    and (rise_from_low <= self.upper_excessive_volatility)  # 저점 대비 최소 상승률 - 상승 여력 시작 지점
                    and fall_from_high >= self.lower_excessive_volatility  # 고점 대비 최대 하락률 - 이미 크게 하락한 종목은 추세 전환 점
                    and close_price > MA_value * self.MA_weight 
                    and trend != 'down'
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
    def set_SLTP(self, df, trend):
        df['log_return'] = np.log(df['close'] / df['close'].shift(1)) * 100
        mean_return = df['log_return'].mean()
        std_return = df['log_return'].std()
        
        if trend == 'up':
            stop_loss = mean_return - (std_return) * self.num_SLTP
            take_profit = abs(stop_loss) * 2
        
        else:
            stop_loss = mean_return - (std_return) * self.num_SLTP
            take_profit = abs(stop_loss) * 1.5
        
        if not (-10.0 <= stop_loss <= -5):
            stop_loss = -5
            take_profit = abs(stop_loss) * 1.5
            
        return mean_return, std_return, stop_loss, take_profit
     
    # ======================================================================================
    def place_buy_orders(self, close):
        investment_per_order = (self.krw_balance / self.num_orders) * (1 - self.pee)
        
        for i in range(self.num_orders):
            if i == 0:  # 첫 번째 주문은 시장가 주문
                try:
                    # 시장가 주문: 주문 금액(investment_per_order) 기준
                    resp = self.upbit.buy_market_order(self.target_ticker, investment_per_order)
                    time.sleep(1)
                    if 'uuid' in resp:
                        # 시장가 주문의 경우 체결 가격은 즉시 확인 불가, 주문 내역 저장
                        self.active_orders.append({
                            'uuid': resp['uuid'],
                            'created_at': datetime.datetime.now(),
                            'ticker': self.target_ticker,
                            'price': None,  # 시장가 주문은 체결 가격 미리 알 수 없음
                            'volume': None  # 체결 수량도 즉시 알 수 없음
                        })
                        print(f"시장가 매수 주문: {self.target_ticker} - 주문 금액: {investment_per_order:,.2f} 원")
                    else:
                        print("시장가 매수 주문 실패")
                        
                except Exception as e:
                    print(f"시장가 매수 주문 오류: {e}")
                    
            else:  # 나머지 주문은 지정가 주문
                # 기본 order_price 계산
                order_price = close * (1 - (i - 1) * self.price_interval)  # i-1로 조정하여 가격 간격 유지
                
                # 호가 단위에 맞게 조정
                tick_size = get_tick_size(order_price)
                adjusted_order_price = (order_price // tick_size) * tick_size
                
                if adjusted_order_price >= 100:
                    adjusted_order_price = round(adjusted_order_price, 0)
                else:
                    adjusted_order_price = round(adjusted_order_price, 8)
                
                # 조정된 가격으로 주문 수량 계산
                order_volume = investment_per_order / adjusted_order_price
                
                try:
                    resp = self.upbit.buy_limit_order(self.target_ticker, adjusted_order_price, order_volume)
                    time.sleep(1)
                    if 'uuid' in resp:
                        self.active_orders.append({
                            'uuid': resp['uuid'],
                            'created_at': datetime.datetime.now(),
                            'ticker': self.target_ticker,
                            'price': adjusted_order_price,
                            'volume': order_volume
                        })
                        print(f"지정가 매수 주문: {self.target_ticker} - 가격: {adjusted_order_price:.2f}, 수량: {order_volume:.2f}")
                    else:
                        print("지정가 매수 주문 실패")
                        
                except Exception as e:
                    print(f"지정가 매수 주문 오류: {e}")
        
        # 거래 발생 플래그 설정
        self.trade_occurred_since_selection = True
        self.hold = True
    
    # ======================================================================================
    def place_sell_order(self):
        resp = self.upbit.sell_market_order(self.target_ticker, self.target_balance)
        
        try :
            if self.target_ticker:
                orders = self.upbit.get_order(self.target_ticker, state="wait")
                for order in orders:
                    self.upbit.cancel_order(order['uuid'])

                self.uncommitted_amount = 0
            else:
                print("미체결된 주문 내역이 존재하지 않습니다")
                    
        except Exception as e:
            print(f"미체결 주문 처리 중 오류: {e}")
            
        self.op_mode = False
        self.hold = False
        self.target_ticker = None
        
        self.seed_ratio = 0.0
        
        # 거래 발생 플래그 설정
        self.trade_occurred_since_selection = True
        
        self.eligible_tickers = []
          
    # ======================================================================================
    def start_trading(self):
        try:
            print("\n!!! 트레이딩 시스템 시작 !!!\n")
            
            while True:                   
                '''
                선정된 종목에 대한 손/익절 기준을 동적으로 설정합니다
                '''
        
                # =========================================
                # 1. No position 상태 (== 원화만 보유한 상태)
                # =========================================
                if not self.target_ticker and self.op_mode == True and self.hold == False and self.seed_ratio == 0.0 :
                                        
                    # 종목 탐색 시작
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
                            close_price = df.tail(1)['close'].values[0]
                            low_price = df.tail(2)['low'].values[0]
                            
                            # 볼린저 밴드 정보 
                            bband_lower_1 = df.tail(1)['BBAND_LOWER'].values[0]
                            bband_lower_2 = df.tail(2)['BBAND_LOWER'].values[0]
                            
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
                            if ((close_price <= bband_lower_1 or low_price <= bband_lower_2) and
                                (slowk_2 <= self.stoch_rsi_buy and slowd_2 <= self.stoch_rsi_buy) and 
                                ((slowk_2 > slowd_2 and slowk_3 < slowd_3) or (slowk_3 > slowd_3 and slowk_4 < slowd_4)) and
                                # WR <= self.WR_buy and
                                MACD_1 > MACD_signal_1 and MACD_2 < MACD_signal_2):
                                
                                signal_tickers.append(ticker_info)
                        
                        except Exception as e:
                            print(f"{ticker} 신호 확인 중 오류: {e}")
                            continue
                        
                        if signal_tickers:
                            selected_ticker_info = max(signal_tickers, key=lambda x: x['volume'])
                            self.target_ticker = selected_ticker_info['ticker']
                            print(f"선정된 종목: {self.target_ticker}")

                        else:
                            print(f"{datetime.datetime.now()} | 현재 거래 신호가 탐색되지 않았습니다")
                
                if self.target_ticker and self.op_mode == True and self.hold == False and self.seed_ratio == 0.0 :
                    target_ticker_df = pyupbit.get_ohlcv(self.target_ticker, f"minute{self.time_scale}", count=self.MA_length)
                    
                    if target_ticker_df is None or len(target_ticker_df) < self.MA_length:
                        continue

                    target_ticker_df = generate_technical_analysis_indicators(target_ticker_df)
                    target_ticker_df[f'MA_{self.MA_length}'] = talib.SMA(target_ticker_df['close'], self.MA_length)

                    # 현재 가격
                    close_price = target_ticker_df.tail(1)['close'].values[0]
                    low_price = target_ticker_df.tail(2)['low'].values[0]
                    
                    # 볼린저 밴드 정보 
                    bband_lower_1 = target_ticker_df.tail(1)['BBAND_LOWER'].values[0]
                    bband_lower_2 = target_ticker_df.tail(2)['BBAND_LOWER'].values[0]
                    
                    # 스토캐스틱 RSI
                    slowk_2 = target_ticker_df.tail(2)['slowk'].values[0]
                    slowd_2 = target_ticker_df.tail(2)['slowd'].values[0]
                    
                    slowk_3 = target_ticker_df.tail(3)['slowk'].values[0]
                    slowd_3 = target_ticker_df.tail(3)['slowd'].values[0]
                    
                    slowk_4 = target_ticker_df.tail(4)['slowk'].values[0]
                    slowd_4 = target_ticker_df.tail(4)['slowd'].values[0]
                    
                    # William R%
                    # WR = target_ticker_df.tail(1)['WR'].values[0]
                    
                    # MACD
                    MACD_1 = target_ticker_df.tail(1)['MACD'].values[0]
                    MACD_signal_1 = target_ticker_df.tail(1)['MACD_signal'].values[0]
                    
                    MACD_2 = target_ticker_df.tail(2)['MACD'].values[0]
                    MACD_signal_2 = target_ticker_df.tail(2)['MACD_signal'].values[0]

                    # Check buy signal
                    if ((close_price <= bband_lower_1 or low_price <= bband_lower_2) and
                        (slowk_2 <= self.stoch_rsi_buy and slowd_2 <= self.stoch_rsi_buy) and 
                        ((slowk_2 > slowd_2 and slowk_3 < slowd_3) or (slowk_3 > slowd_3 and slowk_4 < slowd_4)) and
                        # WR <= self.WR_buy and
                        MACD_1 > MACD_signal_1 and MACD_2 < MACD_signal_2):
                                                                                                     
                        print(f"\n매수 신호 발생: {self.target_ticker} (거래량: {selected_ticker_info['volume']:,.2f})\n")
                    
                        self.place_buy_orders(target_ticker_df['close'].iloc[-1])
                        print("\n원활한 거래를 위해 매수 이후 시스템을 10초 동안 대기합니다...\n")
                        time.sleep(10)
                        
                        # 매수 후 계좌 정보 및 미체결 주문 업데이트
                        print("매수 후 계좌 정보 업데이트 시작")
                        self.update_account_info()
                                            
                    else:
                        print(f"{datetime.datetime.now()} | 현재 거래 신호가 탐색되지 않았습니다")
                
                # =========================================
                # 2. position 진입 상태 (추가 매수 or 매도)
                # =========================================         
                if self.target_ticker and self.op_mode == True and self.hold == True and self.seed_ratio > 0 :
                    
                    # 계좌 정보 업데이트
                    self.balance = self.upbit.get_balances()
                    
                    # 원화 정보 조회 및 보유량 load
                    self.krw_data = [item for item in self.balance if item['currency'] == 'KRW' and float(item['balance']) >= 100]
                    self.krw_balance = int(float(self.krw_data[0]['balance'])) if self.krw_data else 0
                    
                    # 거래 대상 ticker 정보 조회 및 보유량 load
                    self.target_ticker_data = [item for item in self.balance if item['currency'] != 'KRW' and float(item['avg_buy_price']) >= 0.0001 and float(item['balance']) >= 1]
                    self.target_balance = float(self.target_ticker_data[0]['balance']) if self.target_ticker_data else 0
                                            
                    if self.target_ticker_data:
                       
                        self.avg_buy_price = float(self.target_ticker_data[0]['avg_buy_price'])
                        self.buy_ticker_price = pyupbit.get_orderbook(self.target_ticker)['orderbook_units'][0]['ask_price']
                        self.profit_rate = ((self.buy_ticker_price - self.avg_buy_price) / self.avg_buy_price) * 100
                        
                        total_invested = 0
                        for item in self.target_ticker_data:
                            currency = item['currency']
                            ticker = f"KRW-{currency}"
                            balance = float(item['balance'])
                            avg_buy_price = float(item['avg_buy_price'])
                            invested_amount = balance * avg_buy_price
                            total_invested += invested_amount

                        # 거래 대상에 대한 미체결 주문 내역 조회
                        orders = self.upbit.get_order(self.target_ticker, state="wait")
                        self.uncommitted_amount = sum(float(item['price']) * float(item['volume']) for item in orders)
                        
                        # 총 투자 원금 조회
                        total_capital = self.krw_balance + total_invested + self.uncommitted_amount
                        self.total_capital = total_capital
                        
                        # 진입 시드 비율 조회
                        self.seed_ratio = invested_amount / total_capital
                            
                    target_ticker_df = pyupbit.get_ohlcv(self.target_ticker, f"minute{self.time_scale}", count=self.MA_length)                                  
                    target_ticker_df = generate_technical_analysis_indicators(target_ticker_df)
                    target_ticker_df[f'MA_{self.MA_length}'] = talib.SMA(target_ticker_df['close'], self.MA_length)

                    trend = generate_trend(target_ticker_df)
                    
                    # Set stop-loss and take-profit
                    _ , _ , self.stop_loss, self.take_profit = self.set_SLTP(target_ticker_df, trend)
                    
                    # 현재 가격
                    close_price = target_ticker_df.tail(1)['close'].values[0]
                    high_price = target_ticker_df.tail(2)['high'].values[0]
                    
                    # 볼린저 밴드 정보 
                    bband_upper_1 = target_ticker_df.tail(1)['BBAND_UPPER'].values[0]
                    bband_upper_2 = target_ticker_df.tail(2)['BBAND_UPPER'].values[0]
                    
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
                                                                                  
                    # =========================================
                    # 추가 거래 신호 탐색 (매도 조건)
                    # =========================================                                            
                    # 매도 조건 1. 익절
                    if (0 < self.seed_ratio and
                          (close_price >= bband_upper_1 or high_price >= bband_upper_2) and
                          (slowk_2 >= self.stoch_rsi_sell and slowd_2 >= self.stoch_rsi_sell) and 
                          (slowk_2 < slowd_2 and slowk_3 > slowd_3) and
                          # WR >= self.WR_sell and
                          self.profit_rate >= self.take_profit / 2) or (self.profit_rate >= self.take_profit):
                        
                        print(f"\n매도 신호 발생\n")
                        
                        print("<Technical Analysis>")
                        print(f"매도 조건 1 : 현재가격({close_price})이 볼린저밴드의 상단을 터치")
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
                        print(f"{datetime.datetime.now()} | Ticker : {self.target_ticker} | Trend : {trend} | 포지션 진입 비율 {self.seed_ratio * 100:.2f}% | 수익률 {self.profit_rate:.2f}% | 손절가: {self.stop_loss:.2f}% | 익절가: {self.take_profit:.2f}% | 현재 거래 신호가 탐색되지 않았습니다")                     
                                            
                if self.op_mode == False and self.hold == False and self.seed_ratio == 0.0:
                    
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
                
        except Exception as e:
            print(f"트레이딩 중 오류 발생: {e}")