from common_Import import *
from utils.Generate_plot_and_indicators import *  # plot_candles 함수를 올바르게 임포트

'''
<OpenAPI key관리>
트레이딩 시스템을 실행하기 전, 본인의 업비트 계정에 로그인을 해야합니다

계정 로그인을 위해 회원가입 및 UPBIT 보안인증을 마치고, OpenAPI 사용을 신청해 본인의 Secret key와 Access key를 발급받으세요

이 때, Access key는 발급 이후에도 조회를 통해서 확인이 가능하지만 Secret key는 최초 1회에 한 해서 발급이되고 추가적인 확인이 불가능합니다

반드시 Secret key는 발급 이후 메모장과 같은 별도의 공간에 저장해두세요

txt파일에 본인의 Access key, Secret key 순서로 2개의 행으로 나눠 작성한 후 저장하세요(txt파일의 이름은 본인 마음대로 지정하셔도 됩니다)

<주의 사항>
전체 코드의 모든 부분은 필요에 따라서 수정이 가능하니, 자유롭게 활용하셔도 됩니다.

단, 일부 코드의 경우 수정과정에서 오류가 발생할 수 있으니 유의하여 사용하세요.

아래 코드에서 시각화 부분을 함께 활용할 경우엔 차트를 생성하는 과정에서 시간이 소요되어 1초마다 데이터를 갱신하는 것엔 무리가 있습니다.

차트와 함께 거래가 수행되는 과정을 바라보면 좋겠지만, 시간이 딜레이되어 실시간 거래에 리스크 요소가 생기게됩니다.

또한, 다양한 시간대와 범위를 모두 활용하면 좋겠지만, 그 만큼 더 많은 시간이 딜레이되어 거래가 수행되는 과정에 제약이 생길 수 있습니다.

적절한 균형을 맞출 필요가 있으니 잘 고민해보고 사용하길 바랍니다.

'''


class Upbit_trading_system(QAxWidget):
    def __init__(self):
        super().__init__()
        
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f'{current_time} : 업비트 OpenAPI를 사용해 계좌정보에 접근합니다.\n')
        
        self.upbit = None
        
        '''
        <변수 설명>
        
        아래 변수에서 거래를 원하는 ticker, 거래에 사용할 분봉 시간 단위, 추세 정의를 위한 기간 등이 설정 가능합니다.
        
        추세 정의를 위한 기간(2)에서 짧게 기간을 설정할수록 긴 기간에 비해 상대적으로 빈번한 거래를 수행하겠지만 무조건은 아닙니다.
        
        손절 및 익절 기준(3)에서 너무 높은 익절 기준을 하면 수익 실현 기회를 잃겠지만, 너무 낮은 기준을 설정하면 초과 수익의 기회를 잃을 수 있습니다.
        
        포지션 진입 및 청산을 위한 기준(4)은 크게 아래와 같습니다.
         i. 이동평균선의 정렬
         ii. 모멘텀의 둔화
         iii. 볼린저 밴드의 상/하단 터치
         iv. rsi 지표 값 -> rsi 산출을 위한 기간은 14이지만 우리 시스템에선 12만큼만 사용합니다 #TA추가되는 utils에서 수정된 내용
         v. 손절 및 익절 기준(3)의 조건 이행
        
        여기서, 가장 세밀하게 값을 설정해야하는 부분은 rsi이기 때문에 해당 부분만 init부분에서 별도 정의합니다.
        
        
        <시장 특징에 대한 이해설명>
        거래에서 사용되는 분봉 단위(5분, 10분 등)에 따라서 기술적 지표의 민감도가 바뀝니다.
        
        이는 해당 시스템에서 사용되는 지표를 포함한 모든 지표에 해당하는 내용입니다.
        
        예를 들어 분봉 단위를 크게 잡을수록 지표에 함축적으로 포함되는 값이 많기에 둔감하게 산출되고, 작게 잡을수록 더 민감하게 산출될겁니다.
        
        '''
        #### 1. 사용자 정의 변수 지정 ####
        # 거래 ticker
        self.target_ticker = "KRW-SUI"
                    
        #### 2. 거래에서 사용하기 위한 캔들 개수 ####
        self.time_sequence = "minute10"
        self.num_long_period = 6 * 24 * 2
        self.num_medium_period = 6 * 24 * 1
        self.num_short_period = 6 * 12 * 1      
        
        #### 3. 손절 및 익절 기준 변수 설정 ####
        self.stop_loss_threshold = -7.0  # 손절 기준
        
        self.stop_loss_overrated_threshold = -7.0 # 고평가 손절 기준
        self.take_profit_overrated_threshold = 2.0 # 고평가 익절 기준
        self.take_profit_overrated_threshold_uptrend = 3.5 # 고평가 익절 기준(상승장)
        
        self.take_profit_threshold = 2.0  # 익절 기준
        self.take_profit_threshold_uptrend = 3.5  # 익절 기준(상승장)
        
        #### 4. 포지션 진입 및 청산에 사용할 기준 변수 ####
        # 1차 포지션 기준 (매수 기준만 존재)
        self.first_buy_rsi_fanic = 15 # 매수 기준(패닉셀)
        self.first_buy_rsi = 28 # 매수 기준 (횡보장, 상승장)
        
        # 2차 포지션 기준 (매수 + 매도 기준)
        self.second_buy_rsi_fanic = 15 # 매수 기준(패닉셀)        
        self.second_buy_rsi = 23 # 매수 기준 (횡보장)

        self.second_sell_rsi = 65 # 매도 기준 (횡보장)
        self.second_sell_rsi_uptrend = 75 # 매도 기준(상승장)
        
        # 3차 포지션 기준 (매도 기준만 존재)
        self.third_sell_rsi_downtrend = 55 # 매도 기준(하락장에서 본절을 위한 수치)
        self.third_sell_rsi = 65 # 매도 기준 (고평가 매도 기준)
        self.third_sell_rsi_uptrend = 75 # 매도 기준(상승장)
        
        
        #=============================================================================================
        '''
        아래는 시스템 동작을 위한 변수입니다 (수정 X)
        '''     
        #### 거래에 활용하기 위한 변수 정의 ####       
        self.balance = 0 # 현재 계좌 정보
        self.pee = 0.005 # 수수료
                
        self.krw_data = 0 # 계좌 현금 정보
        self.krw_balance = 0 # 계좌 현금 보유량
        
        self.target_ticker_data = 0 # 대상 종목 정보
        self.target_balance = 0 # 대상 종목 보유량
        
        self.target_ticker_order_books = 0 # 보유 종목의 호가창 정보
        
        self.op_mode = False # 시스템 실행 전 계좌정보를 불러오기 위해 잠시 시스템을 중지하는 변수
        self.hold = False # 1차 매수 이후 홀딩 변수
        self.seed_ratio = 0 # 진입한 시드의 비율을 확인
        
        
        self.avg_buy_price = 0 # target 종목 매수평균가
        self.buy_ticker_price = 0 # target 종목 현재가격
        self.profit_rate = 0 # target 종목 현재 수익률
                
        #### 업비트 OpenAPI 접속관련 함수 모음 ####        
        try:
            self.upbit_login()
            self.get_account_info()
            self.start_trading()
            
        except Exception as e:
            print(f"시스템 초기화 중 오류 발생: {e}")
    
    # ----------------------------------------------------------------------------------
    # 업비트 계좌 로그인 
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

     
    # 업비트 잔고 정보 조회
    def get_account_info(self):
        '''
        이 부분은 트레이딩 시스템을 시작했을 때 원활한 거래 수행을 이어가기 위해서 현재 본인의 거래상태를 업데이트하는 부분입니다.
            
        만약, 현재 보유하고 있는 종목의 시드 진입 비율에 따라 거래를 위한 변수를 재정의하는 과정입니다.
       
        '''
        
        try:
            print("\n----계좌 내 잔고 정보 조회 부분----\n")
            self.balance = self.upbit.get_balances()
            
            # 원화 정보 조회 및 보유량 load
            self.krw_data = [item for item in self.balance if item['currency'] == 'KRW' and float(item['balance']) >= 100000]
            self.krw_balance = int(float(self.krw_data[0]['balance'])) if self.krw_data else None
            
            # 거래 대상 ticker 정보 조회 및 보유량 load
            self.target_ticker_data = [item for item in self.balance if item['currency'] != 'KRW' and float(item['avg_buy_price']) >= 1 and float(item['balance']) >= 1]
            self.target_balance = float(self.target_ticker_data[0]['balance']) if self.target_ticker_data else None

            # 거래 대상 ticer를 보유한 경우 
            if self.target_balance:
                self.avg_buy_price = float(self.target_ticker_data[0]['avg_buy_price'])
                self.target_ticker_order_books = pyupbit.get_orderbook(f"{self.target_ticker}")
                self.buy_ticker_price = self.target_ticker_order_books['orderbook_units'][0]['ask_price']
                self.profit_rate = ((self.buy_ticker_price - self.avg_buy_price) / self.avg_buy_price) * 100
            else:
                self.profit_rate = None
            
            # ----------------------------------------------------------------------------------
            if self.krw_balance and not self.target_balance:
                print('현재 상태: 원화만 보유 중입니다.')
                print('현재 보유 시드:', self.krw_balance)
                self.op_mode = True
                self.hold = False
                self.seed_ratio = 0.0
                
            elif self.krw_balance and self.target_balance:
                print('현재 상태: 분할 거래 상태입니다.')
                print('현재 보유 시드:', self.krw_balance)
                print(f"현재 보유 종목: {self.target_ticker} | 현재 수익률 : {self.profit_rate:.2f}%")
                self.op_mode = True
                self.hold = True
                self.seed_ratio = 0.5
                
            elif not self.krw_balance and self.target_balance:
                print('현재 상태: 모든 시드가 진입된 상태입니다.')
                print(f"현재 보유 종목: {self.target_ticker} | 현재 수익률 : {self.profit_rate:.2f}")
                self.op_mode = True
                self.hold = True
                self.seed_ratio = 1.0
            else:
                print('계좌에 아무런 잔고가 없습니다.')
                
            print(f"\n손절 조건은 {self.stop_loss_threshold}% 입니다\n")
            print(f"\n익절 조건은 {self.take_profit_threshold}% 입니다\n")
            print(f"\n상승장에서 상향 조정된 익절 조건은 {self.take_profit_threshold_uptrend}% 입니다\n")
            
        except Exception as e:
            print(f"계좌 정보 조회 중 오류 발생: {e}")   
        
                             
    # ----------------------------------------------------------------------------------
    # 해당 시점부터 거래를 수행하는 부분입니다.
    def start_trading(self):
        try:      
            plt.ion()  # Interactive mode on

            while True:
                '''
                시장의 단기, 중기, 장기 추세를 판단하고 종합적인 최종 추세를 판단하는 부분입니다.
                
                '''
                target_ticker_df_long = pyupbit.get_ohlcv(self.target_ticker, self.time_sequence, count=self.num_long_period)
                target_ticker_df_medium = target_ticker_df_long.tail(self.num_medium_period).copy()
                target_ticker_df_short = target_ticker_df_long.tail(self.num_short_period).copy()
                            
                        
                dataframes = [target_ticker_df_long,
                            target_ticker_df_medium,
                            target_ticker_df_short                     
                            ]
                
                timeframes = [f"Long Period ({self.num_long_period / (6 * 24)} Day)",
                            f"Midium Period ({self.num_medium_period / (6 * 24)} Day)", 
                            f"Short Period ({self.num_short_period / (6 * 24)} Day)"                           
                            ]
                
                trend_results = []
                        
                for i in range(len(dataframes)):
                    trend = generate_trend(dataframes[i])                
                    trend_results.append(f"{timeframes[i]}: {trend}")        
                
                # 현재 시간을 가져와서 trend_results에 추가
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                trend_results.insert(0, f"Current Time: {current_time}")

                # 트렌드 결과를 종합해 최종 추세를 확인      
                final_trend = determine_final_trend(trend_results, trend_combinations)
                
                # print(" | ".join(trend_results), f"| Final Trend: {final_trend}")
                # -----------------------------------------------------------------------------------------------------------------------------------------------
                '''
                해당 부분은 거래 수행을 위해 사용되는 차트 별로 하나의 plt에 시각화하여 가격 변동을 확인하는 부분입니다    
                        
                시각화 창을 실수로 닫더라도, 다시 켜질 수 있도록 코드를 설계했으니 필요에 따라 수정해도 괜찮습니다
                
                단, 시각화 창을 띄울 경우 차트를 생성하는 시간이 소요되기 때문에 거래과정이 많이 방해됩니다.
                
                시스템을 실행하시기 전에 추세에 대한 판단이 정말 맞는지 의심이 되셔서 확인하고 싶으신 분들을 위해 만들어 놓은 부분입니다.
                
                확인하신 이후엔 사용하지 않는 방향으로 권장합니다.
                            
                '''
                        
                ''' if not plt.get_fignums():
                    fig, axes = plt.subplots(1, len(dataframes), figsize=(20, 8))
                    fig.tight_layout(pad=1.0)
                
                for i, ax in enumerate(axes.flatten()):
                    ax.clear()
                    plot_candles(dataframes[i], trend_line=True, mean_std_line = True, volume_bars=False, title=f"{timeframes[i]} Chart", ax=ax)
                    
                plt.pause(1)  # Pause for 1 second to allow for the update
                fig.canvas.draw()  # Draw the canvas to update the figure
                
                if not plt.get_fignums():
                    plt.close(fig) '''
                
                # -----------------------------------------------------------------------------------------------------------------------------------------------
                '''            
                해당 부분이 앞으로의 트레이딩 시스템을 실행하기 위해서 기술적 지표를 생성하는 공간입니다            
                지표는 새롭게 정의하여 자유롭게 활용이 가능합니다         
                '''         

                # 기술적 지표 추가
                target_ticker_df_long = generate_technical_analysis_indicators(target_ticker_df_long)
                
                # MOM의 추세 파악 (추세 전환 확인을 위함) -> 근데 굳이 사용 안 함
                # target_ticker_df_long = add_mom_trend_column(target_ticker_df_long, self.num_long_period)
                
                # 기술적 지표 추가(단기, 중기, 장기 EMA)
                target_ticker_df_long['EMA_10'] = target_ticker_df_long['close'].ewm(span=10, adjust=False).mean()
                target_ticker_df_long['EMA_20'] = target_ticker_df_long['close'].ewm(span=20, adjust=False).mean()
                target_ticker_df_long['EMA_50'] = target_ticker_df_long['close'].ewm(span=50, adjust=False).mean()              
                
                # 거래 수행을 위한 가격 정보 load
                close = target_ticker_df_long.tail(1)['close'].values[0]
                bband_lower = target_ticker_df_long.tail(1)['BBAND_lOWER'].values[0]
                bband_upper = target_ticker_df_long.tail(1)['BBAND_UPPER'].values[0]
                rsi = target_ticker_df_long.tail(1)['RSI'].values[0]
                mom = target_ticker_df_long.tail(1)['MOM'].values[0]
                ema_10 = target_ticker_df_long.tail(1)['EMA_10'].values[0]
                ema_20 = target_ticker_df_long.tail(1)['EMA_20'].values[0]
                ema_50 = target_ticker_df_long.tail(1)['EMA_50'].values[0]
                
                # -----------------------------------------------------------------------------------------------------------------------------------------------
                # 1차 : 최초 매수시도
                '''
                자동화 매매의 목적은 한 번에 큰 수익을 실현하는 것이 아니라, 리스크 부담을 최소화하면서 천천히 수익을 누적하는 것입니다.   
                
                가장 기본이 되는 거래 방식은 기술적 분석 결과에서 과매도 상태가 판단되면 거래를 수행하는 방식입니다.
                
                즉, 상대적으로 저평가가 된 신호를 인식하는 것입니다.
                
                각 추세 별 시장 상황에 맞춰 분석 방식은 서로 다르게 설계됐으며, 불필요한 포지션 진입을 방지하도록 설계됐습니다.
                
                하락장에선 기본적으로 매수를 시도하지 않습니다.  
                        
                그러나, 하락장의 끝자락에 접근했을 때 저점을 잡기 위해서 볼린저 밴드와 RSI 지표를 사용해 매수를 시도합니다.
                                        
                RSI라는 지표는 특정 범위 안에서 변동되며 천장 혹은 바닥으로 치솟는 경우가 흔하게 발견되는 것은 아닙니다.
                
                추세가 하락장이란 것은 투자자 입장에서 파악할 수 없는 추가 하락여력이 남아있을 수 있다고 해석할 수 있습니다.
                
                따라서, 매수를 위한 RSI 기준선을 굉장히 보수적(낮은값)으로 잡습니다.

                하락장을 제외한 횡보장과 상승장은 상대적으로 공격적인 전략이 적용됩니다.
                                
                '''
                if self.op_mode ==True and self.hold == False and self.seed_ratio == 0.0:
                    
                    # 계좌 정보 업데이트
                    self.balance = self.upbit.get_balances()
                    
                    # 원화 정보 조회 및 보유량 load
                    self.krw_data = [item for item in self.balance if item['currency'] == 'KRW' and float(item['balance']) >= 100000]
                    self.krw_balance = int(float(self.krw_data[0]['balance'])) if self.krw_data else None
                    
                    # 거래 대상 ticker 정보 조회 및 보유량 load
                    self.target_ticker_data = [item for item in self.balance if item['currency'] != 'KRW' and float(item['avg_buy_price']) >= 1 and float(item['balance']) >= 1]
                    self.target_balance = float(self.target_ticker_data[0]['balance']) if self.target_ticker_data else None
                    
                    if final_trend == "down":
                        if close <= bband_lower and rsi <= self.first_buy_rsi_fanic:
                                       
                            print(f"\n매수 신호 발생\n")
                            print(f"\n하락장 : 패닉셀\n")
                            
                            print("<Technical Analysis>")
                            print(f"매수 조건 1 : 현재가격({close})이 볼린저밴드의 하단({bband_lower:.2f})을 터치")
                            print(f"매수 조건 2 : RSI({rsi:.2f})가 패닉셀 매수기준({self.first_buy_rsi_fanic}) 이하")
                                                        
                            buy_price = (self.krw_balance / 2) * (1 - self.pee)
                            self.upbit.buy_market_order(self.target_ticker, buy_price)
                            self.seed_ratio = 0.5
                            self.hold = True
                            
                            print("+------------------+")
                            print("!!!   매수성공   !!!")
                            print("+------------------+")

                            # 매수 후 10초 대기
                            print("\n원활한 거래를 위해 매수 이후 시스템을 10초 동안 대기합니다...\n")
                            time.sleep(10)
                        
                        else :
                            print(f"{current_time} | Ticker : {self.target_ticker} | Final Trend : {final_trend} | 포지션 진입 비율 {self.seed_ratio * 100}% | 현재 하락장이므로 포지션 진입을 하지 않습니다")
                    
                    elif final_trend == "sideway":
                        if close <= bband_lower and rsi <= self.first_buy_rsi and ema_10 < ema_20 :
                            
                            print(f"\n매수 신호 발생\n")
                            print(f"\n횡보장\n")
                            
                            print("<Technical Analysis>")
                            print(f"매수 조건 1 : 현재가격({close})이 볼린저밴드의 하단({bband_lower:.2f})을 터치")
                            print(f"매수 조건 2 : RSI({rsi:.2f})가 매수기준({self.first_buy_rsi}) 이하")
                            print(f"매수 조건 3 : 이평선 정렬(단기 : {ema_10:.2f} 중기 : {ema_20:.2f})")
                            
                            buy_price = (self.krw_balance / 2) * (1 - self.pee)
                            self.upbit.buy_market_order(self.target_ticker, buy_price)
                            self.seed_ratio = 0.5
                            self.hold = True
                            
                            print("+------------------+")
                            print("!!!   매수성공   !!!")
                            print("+------------------+")

                            # 매수 후 10초 대기
                            print("\n원활한 거래를 위해 매수 이후 시스템을 10초 동안 대기합니다...\n")
                            time.sleep(10)

                        else:
                            print(f"{current_time} | Ticker : {self.target_ticker} | Final Trend : {final_trend} | 포지션 진입 비율 {self.seed_ratio * 100}% | 현재 횡보장에서 매수조건이 모두 충족되지 않아 포지션 진입을 하지 않습니다")
                        
                    elif final_trend == "up":
                        if rsi <= self.first_buy_rsi and ema_10 < ema_20:
                            
                            print(f"\n매수 신호 발생\n")
                            print(f"\n상승장\n")
                            
                            print("<Technical Analysis>")
                            print(f"매수 조건 1 : RSI({rsi:.2f})가 매수기준({self.first_buy_rsi}) 이하")
                            print(f"매수 조건 2 : 이평선 정렬(단기 : {ema_10:.2f} 중기 : {ema_20:.2f})")
                            
                            buy_price = (self.krw_balance / 2) * (1 - self.pee)
                            self.upbit.buy_market_order(self.target_ticker, buy_price)
                            self.seed_ratio = 0.5
                            self.hold = True
                            
                            print("+------------------+")
                            print("!!!   매수성공   !!!")
                            print("+------------------+")
                            
                            # 매수 후 10초 대기
                            print("\n원활한 거래를 위해 매수 이후 시스템을 10초 동안 대기합니다...\n")
                            time.sleep(10)
                            
                        else :
                            print(f"{current_time} | Ticker : {self.target_ticker} | Final Trend : {final_trend} | 포지션 진입 비율 {self.seed_ratio * 100}% | 현재 사승장에서 매수조건이 모두 충족되지 않아 포지션 진입을 하지 않습니다")

                # -----------------------------------------------------------------------------------------------------------------------------------------------
                # 2차 : 매도 혹은 추가 매수 시도
                '''
                
                여기서부턴 포지션이 진입된 상태이기 때문에 익절/손절 기준이 거래에 반영됩니다.
                
                각 시장 상황에 대해서 별도의 주석을 입력했으니 확인 바랍니다.                
                
                '''
                if self.op_mode == True and self.hold == True and self.seed_ratio == 0.5:
                    
                    # 계좌 정보 업데이트
                    self.balance = self.upbit.get_balances()
                    
                    # 원화 정보 조회 및 보유량 load
                    self.krw_data = [item for item in self.balance if item['currency'] == 'KRW' and float(item['balance']) >= 100000]
                    self.krw_balance = int(float(self.krw_data[0]['balance'])) if self.krw_data else None
                    
                    # 거래 대상 ticker 정보 조회 및 보유량 load
                    self.target_ticker_data = [item for item in self.balance if item['currency'] != 'KRW' and float(item['avg_buy_price']) >= 1 and float(item['balance']) >= 1]
                    self.target_balance = float(self.target_ticker_data[0]['balance']) if self.target_ticker_data else None

                    # 거래 대상 ticer를 보유한 경우 
                    if self.target_balance:
                        self.avg_buy_price = float(self.target_ticker_data[0]['avg_buy_price'])
                        self.target_ticker_order_books = pyupbit.get_orderbook(f"{self.target_ticker}")
                        self.buy_ticker_price = self.target_ticker_order_books['orderbook_units'][0]['ask_price']
                        self.profit_rate = ((self.buy_ticker_price - self.avg_buy_price) / self.avg_buy_price) * 100
                    else:
                        self.profit_rate = None 
                    
                    # -----------------------------------------------------------------------------------------------------------
                                        
                    if final_trend == 'down':
                        '''
                
                        해당 부분은 하락장 시기에 1차 매수 이후, 2차 거래를 위한 설계부분입니다.
                        
                        1차 매수 당시 하락장에선 기술적분석 결과 패닉셀에 가까운 상황이 인식됐을 때 매수를 시도했습니다.
                        
                        즉, 수행된 1차 매수는 굉장히 저점에 가까운 시기에 시도된 것입니다.
                        
                        따라서, 2차 매수에선 1차로 매수된 포지션을 기준으로 추가 패닉셀이 나온다면 손절, 수익 실현이 가능하다면 익절 시도 합니다.
                        
                        이러한 이유는 하락장에서의 기회 비용을 포착하기 위한 것이며 공격적인 거래방식으로 판단될 수 있습니다.
                        
                        단, 하락장에서 만약 손절 기준의 80% 부근에 도달된 상태로 기술적 분석 상 과매도 신호가 식별되면 평단가를 낮추는 방식으로 추가 매수를 진행합니다.
                        
                        추가 매수를 위한 RSI기준은 1차와 도일하게 설정했습니다 (1차와 동일하거나 더 낮게 설정하면 아마 손절로 이어질 것이기 때문에 분할매수를 시도하는 이유가 희석됨)
                        
                        대부분의 추가 매수는 과매도 평가 혹은 물타기 형태로 이어집니다.
                        
                        '''
                    
                        if self.profit_rate <= self.stop_loss_threshold : 
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n하락장 : 손절\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Earning Rate>")
                            print(f"매도 조건 1 : 수익률({self.profit_rate:.2f}%)이 손절기준({self.stop_loss_threshold}%)에 도달")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                        
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                        
                        elif self.profit_rate >= self.take_profit_threshold:
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n하락장 : 익절\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Earning Rate>")
                            print(f"매도 조건 1 : 수익률({self.profit_rate:.2f}%)이 익절기준({self.take_profit_threshold}%)에 도달")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                        
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                        
                        elif close >= bband_upper and rsi >= self.second_sell_rsi and (self.profit_rate < self.stop_loss_overrated_threshold or self.profit_rate > self.take_profit_overrated_threshold):
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n하락장 : 고평가(익절 or 손절)\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Technical Analysis>")
                            print(f"매도 조건 1 : 현재가격({close})이 볼린저밴드의 상단({bband_upper:.2f})을 터치")
                            print(f"매도 조건 2 : RSI({rsi:.2f})가 매도기준({self.second_sell_rsi}) 이상")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                            
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")  
                                  
                        elif close <= bband_lower and rsi <= self.second_buy_rsi_fanic and ema_10 < ema_20 < ema_50 and self.stop_loss_threshold < self.profit_rate < (self.stop_loss_threshold * 4/5):
                            
                            print(f"\n추가 매수 신호 발생\n")
                            print(f"\n하락장 : 패닉셀\n")
                            
                            print("<Technical Analysis>")
                            print(f"매수 조건 1 : 현재가격({close})이 볼린저밴드의 하단({bband_lower:.2f})을 터치")
                            print(f"매수 조건 2 : RSI({rsi:.2f})가 패닉셀 매수기준({self.second_buy_rsi_fanic}) 이하")
                            print(f"매수 조건 3 : 이평선 정렬(단기 : {ema_10:.2f} 중기 : {ema_20:.2f} 장기 : {ema_50:.2f})")
                            
                            print("<Earning Rate>")
                            print(f"매수 조건 1 : 수익률({self.profit_rate:.2f}%)이 손절기준({self.take_profit_threshold * 4/5}%)에 도달")
                                           
                            buy_price = self.krw_balance* (1 - self.pee)
                            self.upbit.buy_market_order(self.target_ticker, buy_price)
                            self.seed_ratio == 1.0
                            
                            print("+------------------+")
                            print("!!! 추가매수성공 !!!")
                            print("+------------------+")
                            
                            # 매수 후 10초 대기
                            print("\n원활한 거래를 위해 매수 이후 시스템을 10초 동안 대기합니다...\n")
                            time.sleep(10)
                            
                        else :
                            print(f"{current_time} | Ticker : {self.target_ticker} | Final Trend : {final_trend} | 포지션 진입 비율 {self.seed_ratio * 100}% | 현재 수익률 : {self.profit_rate:.2f}% | 추가매수, 매도 조건 중 충족된 상황이 존재하지 않아 포지션을 Holding합니다")
                            
                            
                    elif final_trend == 'sideway':
                        '''
                
                        해당 부분은 횡보장 시기에 1차 매수 이후, 2차 거래를 위한 설계부분입니다.
                        
                        기본적으론 수익률이 원하는 조건에 부합한다면 수익을 실현하도록 설계했습니다.
                        
                        단, 분할매수를 했기 때문에 추가 매수를 통해서 더 큰 수익을 실현할 수 있도록 기술적 분석 상 과매도 상대가 인식되면 추가 매수를 적극적으로 시도합니다.
                                              
                        대신 오류 신호를 제거하기 위해서 횡보장에서는 RSI 기준은 하락장과 다르게 1차 매수 기준보다 낮게 설정합니다
                        
                        횡보장은 상대적으로 하락장에 비해 RSI값이 높게 분포가 됐으니 단기 과매도로 인해서 순간적으로 낮아지는 시기를 적극적으로 활용합니다.
                        
                        단, 횡보장의 시기가 길어진 상태로 거시적 관점에서 하방의 추세로 변하고 있다면 기술적 분석 상 괜찮더라도, 수익률이 하락상태일 수 있습니다.
                        
                        이럴 경우엔 손절가에 도달할 경우 물을 타는 방식으로 진행합니다.
                                                                                                
                        '''
                        
                        if close >= bband_upper and self.profit_rate >= self.take_profit_threshold :
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n횡보장 : 익절\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Technical Analysis>")
                            print(f"매도 조건 1 : 현재가격({close})이 볼린저밴드의 상단({bband_upper:.2f})을 터치")
                            
                            print("<Earning Rate>")
                            print(f"매도 조건1  : 수익률 {self.profit_rate:.2f}%이 익절기준({self.take_profit_threshold})에 도달")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                            
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                           
                        elif self.profit_rate >= (self.take_profit_threshold * 1.5) :
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n횡보장 : 익절*1.5\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Earning Rate>")
                            print(f"매도 조건 1 : 수익률 {self.profit_rate:.2f}%이 익절기준({self.take_profit_threshold})의 1.5배에 도달")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                            
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                        
                        elif close >= bband_upper and rsi >= self.second_sell_rsi and (self.profit_rate < self.stop_loss_overrated_threshold or self.profit_rate > self.take_profit_overrated_threshold) :
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n횡보장 : 고평가(익절 or 손절)\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Technical Analysis>")
                            print(f"매도 조건 1 : 현재가격({close})이 볼린저밴드의 상단({bband_upper:.2f})을 터치")
                            print(f"매도 조건 2 : RSI({rsi:.2f})가 매도기준({self.second_sell_rsi}) 이상")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                            
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")    
                        
                        elif close <= bband_lower and rsi <= self.second_buy_rsi and ema_10 <  ema_20 and self.stop_loss_threshold < self.profit_rate < self.take_profit_threshold:
                            
                            print(f"\n추가 매수 신호 발생\n")
                            print(f"\n횡보장\n")
                            
                            print("<Technical Analysis>") 
                            print(f"매수 조건 1 : 현재가격({close})이 볼린저밴드의 하단({bband_lower:.2f})을 터치")
                            print(f"매수 조건 2 : RSI({rsi:.2f})가 매수기준({self.second_buy_rsi}) 이하")
                            print(f"매수 조건 3 : 이평선 정렬(단기 : {ema_10:.2f} 중기 : {ema_20:.2f})")
                            
                            buy_price = self.krw_balance* (1 - self.pee)
                            self.upbit.buy_market_order(self.target_ticker, buy_price)
                            self.seed_ratio = 1.0
                            
                            print("+------------------+")
                            print("!!! 추가매수성공 !!!")
                            print("+------------------+")
                            
                            # 매수 후 10초 대기
                            print("\n원활한 거래를 위해 매수 이후 시스템을 10초 동안 대기합니다...\n")
                            time.sleep(10)
                        
                        elif close <= bband_lower and rsi <= self.second_buy_rsi_fanic and self.stop_loss_threshold < self.profit_rate < self.take_profit_threshold :
                            
                            print(f"\n추가 매수 신호 발생\n")
                            print(f"\n횡보장 : 패닉셀\n")
                            
                            print("<Technical Analysis>")
                            print(f"매수 조건 1 : 현재가격({close})이 볼린저밴드의 하단({bband_lower:.2f})을 터치")
                            print(f"매수 조건 2 : RSI({rsi:.2f})가 패닉셀 매수기준({self.second_buy_rsi_fanic}) 이하")
                                                  
                            buy_price = self.krw_balance* (1 - self.pee)
                            self.upbit.buy_market_order(self.target_ticker, buy_price)
                            self.seed_ratio = 1.0
                            
                            print("+------------------+")
                            print("!!! 추가매수성공 !!!")
                            print("+------------------+")
                            
                            # 매수 후 10초 대기
                            print("\n원활한 거래를 위해 매수 이후 시스템을 10초 동안 대기합니다...\n")
                            time.sleep(10)
                            
                        elif self.profit_rate < self.stop_loss_threshold :
                            
                            print(f"\n추가 매수 신호 발생\n")
                            print(f"\n횡보장 : 물타기\n")
                            
                            print("<Earning Rate>")
                            print(f"수익률 {self.profit_rate:.2f}%이 손절기준({self.stop_loss_threshold})에 도달")
                            
                            buy_price = self.krw_balance* (1 - self.pee)
                            self.upbit.buy_market_order(self.target_ticker, buy_price)
                            self.seed_ratio = 1.0
                            
                            print("+------------------+")
                            print("!!! 추가매수성공 !!!")
                            print("+------------------+")
                            
                            # 매수 후 10초 대기
                            print("\n원활한 거래를 위해 매수 이후 시스템을 10초 동안 대기합니다...\n")
                            time.sleep(10)
                            
                        else :
                            print(f"{current_time} | Ticker : {self.target_ticker} | Final Trend : {final_trend} | 포지션 진입 비율 {self.seed_ratio * 100}% | 현재 수익률 : {self.profit_rate:.2f}% | 추가매수, 매도 조건 중 충족된 상황이 존재하지 않아 포지션을 Holding합니다")
                                
                            
                    elif final_trend == 'up':
                        '''
                
                        해당 부분은 상승장 시기에 1차 매수 이후, 2차 거래를 위한 설계부분입니다.
                        
                        횡보장에서와 마찬가지로 기본적으론 수익률이 원하는 조건에 부합한다면 수익을 실현하도록 설계했습니다.
                        
                        단, 상승장에선 손실에 대한 우려보단 초과 수익분을 놓치는 것에 대한 우려가 더 크게 작용할 것 입니다.
                        
                        따라서, 기회가 된다면 수익을 실현하겠지만 추격 매수가 가능하다면 적극적으로 진입 시드를 늘리도록 합니다. 
                                                                                                                        
                        '''
                        
                        if (mom <= 0 or rsi >= self.second_sell_rsi_uptrend) and self.profit_rate >= self.take_profit_threshold_uptrend:
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n상승장 : 익절\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Technical Analysis>")
                            print(f"매도 조건 1 : MOM이 0에 도달 혹은 RSI({rsi:.2f})가 매도기준{self.second_sell_rsi_uptrend} 이상")
                            
                            print("<Earning Rate>")
                            print(f"매도 조건 1 : 수익률 {self.profit_rate:.2f}%이 익절기준({self.take_profit_threshold_uptrend})에 도달")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                            
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                        
                        elif self.profit_rate >= (self.take_profit_threshold_uptrend * 2) :
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n상승장 : 익절*2\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                                                        
                            print("<Earning Rate>")
                            print(f"매도 조건 1 : 수익률 {self.profit_rate:.2f}%이 익절기준({self.take_profit_threshold_uptrend})의 2배에 도달")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                            
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                        
                        elif close >= bband_upper and rsi >= self.second_sell_rsi_uptrend and (self.profit_rate < self.stop_loss_overrated_threshold or self.profit_rate > self.take_profit_overrated_threshold_uptrend):
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n상승장 : 고평가(익절 or 손절)\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Technical Analysis>")
                            print(f"매도 조건 1 : 현재가격({close})이 볼린저밴드의 상단({bband_upper:.2f})을 터치")
                            print(f"매도 조건 2 : RSI({rsi:.2f})가 매도기준({self.second_sell_rsi_uptrend}) 이상")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                            
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                                   
                        elif close <= bband_lower and rsi <= self.second_buy_rsi and ema_10 < ema_20 < ema_50 and self.profit_rate < self.take_profit_threshold_uptrend:
                            
                            print(f"\n추가 매수 신호 발생\n")
                            print(f"\n상승장 : 추격매수\n")
                            
                            print("<Technical Analysis>")
                            print(f"매수 조건 1 : 현재가격({close})이 볼린저밴드의 하단({bband_lower:.2f})을 터치")
                            print(f"매수 조건 2 : RSI({rsi:.2f})가 매수기준({self.second_buy_rsi}) 이하")
                            print(f"매수 조건 3 : 이평선 정렬(단기 : {ema_10:.2f} 중기 : {ema_20:.2f} 장기 : {ema_50:.2f})")
                        
                            buy_price = self.krw_balance* (1 - self.pee)
                            self.upbit.buy_market_order(self.target_ticker, buy_price)
                            self.seed_ratio = 1.0
                            
                            print("+------------------+")
                            print("!!! 추가매수성공 !!!")
                            print("+------------------+")
                            
                            # 매수 후 10초 대기
                            print("\n원활한 거래를 위해 매수 이후 시스템을 10초 동안 대기합니다...\n")
                            time.sleep(10)
                        
                        else :
                            print(f"{current_time} | Ticker : {self.target_ticker} | Final Trend : {final_trend} | 포지션 진입 비율 {self.seed_ratio * 100}% | 현재 수익률 : {self.profit_rate:.2f}% | 추가매수, 매도 조건 중 충족된 상황이 존재하지 않아 포지션을 Holding합니다")
                
                # -----------------------------------------------------------------------------------------------------------------------------------------------            
                # 3차 : 전량 매도 시도
                if self.op_mode == True and self.hold == True and self.seed_ratio == 1.0:
                    
                    # 계좌 정보 업데이트
                    self.balance = self.upbit.get_balances()
                    
                    # 이미 모든 시드가 진입된 상태이므로 원화 정보는 조회하지 않습니다
                                        
                    # 거래 대상 ticker 정보 조회 및 보유량 load
                    self.target_ticker_data = [item for item in self.balance if item['currency'] != 'KRW' and float(item['avg_buy_price']) >= 1 and float(item['balance']) >= 1]
                    self.target_balance = float(self.target_ticker_data[0]['balance']) if self.target_ticker_data else None

                    # 거래 대상 ticer를 보유한 경우 
                    if self.target_balance:
                        self.avg_buy_price = float(self.target_ticker_data[0]['avg_buy_price'])
                        self.target_ticker_order_books = pyupbit.get_orderbook(f"{self.target_ticker}")
                        self.buy_ticker_price = self.target_ticker_order_books['orderbook_units'][0]['ask_price']
                        self.profit_rate = ((self.buy_ticker_price - self.avg_buy_price) / self.avg_buy_price) * 100
                    else:
                        self.profit_rate = None
                    
                    # -----------------------------------------------------------------------------------------------------------
                    if final_trend == 'down':                       
                        '''
                
                        해당 부분은 하락장 시기에 모든 시드가 진입된 이후 거래를 위한 설계부분입니다.
                        
                        2차 매수까지 수행됐다면 평단가는 아마 낮춰졌겠지만 더 이상 진입 가능한 시드가 없습니다.
                        
                        따라서, 기본적으론 손절 기준 혹은 익절 기준에 닿았을 때 포지션을 청산하며
                        
                        본절로 시장을 이탈하는 기회를 잡기위해 익절 기준의 1/5에 도달된 상태에서 기술적 지표 상 과매수 상태가 인식됐다면 본절로 포지션을 청산합니다.
                        
                        '''
                        
                        if self.profit_rate <= self.stop_loss_threshold :                          
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n하락장 : 손절\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Earning Rate>")
                            print(f"매도 조건 1 : 수익률({self.profit_rate:.2f}%)이 손절기준({self.stop_loss_threshold}%)에 도달")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)

                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                        
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                        
                        elif self.profit_rate >= self.take_profit_threshold:
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n하락장 : 익절\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Earning Rate>")
                            print(f"매도 조건 1 : 수익률({self.profit_rate:.2f}%)이 익절기준({self.take_profit_threshold}%)에 도달")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                        
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                        
                        elif close >= bband_upper and rsi >= self.third_sell_rsi_downtrend and (self.profit_rate < self.stop_loss_overrated_threshold or self.profit_rate > self.take_profit_overrated_threshold):
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n하락장 : 고평가(익절 or 손절)\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Technical Analysis>")
                            print(f"매도 조건 1 : 현재가격({close})이 볼린저밴드의 상단({bband_upper:.2f})을 터치")
                            print(f"매도 조건 2 : RSI({rsi:.2f})가 매도기준({self.third_sell_rsi_downtrend}) 이상")
                                                        
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                        
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                            
                        else :
                            print(f"{current_time} | Ticker : {self.target_ticker} | Final Trend : {final_trend} | 포지션 진입 비율 {self.seed_ratio * 100}% | 현재 수익률 : {self.profit_rate:.2f}% | 매도 조건 중 충족된 상황이 존재하지 않아 포지션을 Holding합니다")
                        
                        
                    elif final_trend == 'sideway':
                        '''
                
                        해당 부분은 횡보장 시기에 모든 시드가 진입된 이후 거래를 위한 설계부분입니다.
                        
                        모든 시드가 진입됐으므로 익절 혹은 손절 기준에만 맞춰서 거래를 이행합니다.
                        
                        '''
                        
                        if close >= bband_upper and self.profit_rate >= self.take_profit_threshold:
                            print(f"\n매도 신호 발생\n")
                            print(f"\n횡보장 : 익절\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Technical Analysis>")
                            print(f"매도 조건 1 : 현재가격({close})이 볼린저밴드의 상단({bband_upper:.2f})을 터치")
                            
                            print("<Earning Rate>")
                            print(f"매도 조건1  : 수익률 {self.profit_rate:.2f}%이 익절기준({self.take_profit_threshold})에 도달")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                            
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                        
                        
                        elif self.profit_rate >= (self.take_profit_threshold * 1.5) :
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n횡보장 : 익절*1.5\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Earning Rate>")
                            print(f"매도 조건 1 : 수익률 {self.profit_rate:.2f}%이 익절기준({self.take_profit_threshold})의 1.5배에 도달")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                            
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                        
                        elif close >= bband_upper and rsi >= self.third_sell_rsi and (self.profit_rate < self.stop_loss_overrated_threshold or self.profit_rate > self.take_profit_overrated_threshold):
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n횡보장 : 고평가(익절 or 손절)\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Technical Analysis>")
                            print(f"매도 조건 1 : 현재가격({close})이 볼린저밴드의 상단({bband_upper:.2f})을 터치")
                            print(f"매도 조건 2 : RSI({rsi:.2f})가 매도기준({self.third_sell_rsi}) 이상")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                            
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")    
                                
                        elif self.profit_rate < self.stop_loss_threshold :
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n횡보장 : 손절\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Earning Rate>")
                            print(f"매도 조건 1 : 수익률 {self.profit_rate:.2f}%이 손절기준({self.stop_loss_threshold})에 도달")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                            
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                            
                        else :
                            print(f"{current_time} | Ticker : {self.target_ticker} | Final Trend : {final_trend} | 포지션 진입 비율 {self.seed_ratio * 100}% | 현재 수익률 : {self.profit_rate:.2f}% | 매도 조건 중 충족된 상황이 존재하지 않아 포지션을 Holding합니다")
                        
                    
                    elif final_trend == 'up':
                        '''
                
                        해당 부분은 상승장 시기에 모든 시드가 진입된 이후 거래를 위한 설계부분입니다.
                        
                        모든 시드가 진입됐으므로 익절 혹은 손절 기준에만 맞춰서 거래를 이행합니다.
                        
                        '''
                        
                        if self.profit_rate >= self.take_profit_threshold_uptrend and (mom <= 0 or rsi >= self.third_sell_rsi_uptrend):
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n상승장 : 익절\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Technical Analysis>")
                            print(f"매도 조건 1 : MOM이 0에 도달 혹은 RSI({rsi:.2f})가 매도기준({self.third_sell_rsi_uptrend}) 이상")
                            
                            print("<Earning Rate>")
                            print(f"매도 조건 1 : 수익률 {self.profit_rate:.2f}%이 익절기준({self.take_profit_threshold_uptrend})에 도달")
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                            
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                        
                        elif self.profit_rate >= (self.take_profit_threshold_uptrend * 2) :
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n상승장 : 익절*2\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Earning Rate>")
                            print(f"매도 조건 1 : 수익률 {self.profit_rate:.2f}%이 익절기준({self.take_profit_threshold_uptrend})의 2배에 도달")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                            
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")
                        
                        elif close >= bband_upper and rsi >= self.third_sell_rsi and (self.profit_rate < self.stop_loss_overrated_threshold or self.profit_rate > self.take_profit_overrated_threshold_uptrend):
                            
                            print(f"\n매도 신호 발생\n")
                            print(f"\n상승장 : 고평가(익절 or 손절)\n")
                            
                            print(f"수익률 : {self.profit_rate:.2f}%")
                            
                            print("<Technical Analysis>")
                            print(f"매도 조건 1 : 현재가격({close})이 볼린저밴드의 상단({bband_upper:.2f})을 터치")
                            print(f"매도 조건 2 : RSI({rsi:.2f})가 매도기준({self.third_sell_rsi}) 이상")
                            
                            self.upbit.sell_market_order(self.target_ticker, self.target_balance)
                            
                            self.op_mode = False
                            self.hold = False
                            self.seed_ratio = 0.0
                            
                            print("+------------------+")
                            print("!!!   매도성공   !!!")
                            print("+------------------+")    
                            
                        else :
                            print(f"{current_time} | Ticker : {self.target_ticker} | Final Trend : {final_trend} | 포지션 진입 비율 {self.seed_ratio * 100}% | 현재 수익률 : {self.profit_rate:.2f}% | 매도 조건 중 충족된 상황이 존재하지 않아 포지션을 Holding합니다")
                
                # -----------------------------------------------------------------------------------------------------------------------------------------------            
                # 4차 : 익절 or 손절 이후 계좌 정보 업에이트 
                if self.op_mode == False and self.hold == False and self.seed_ratio == 0.0:
                    print("\n매도가 진행되어 계좌 정보를 업데이트 하겠습니다 \n")
                    self.get_account_info()
                    
                    # 10초 대기 시간을 추가합니다.
                    print("거래 준비를 위해 10초 대기합니다...\n")
                    time.sleep(10)
                    
                    print("거래를 시작합니다\n")
                            
        except Exception as e:
            print(f"트레이딩 중 오류 발생: {e}")
            
        
         