import requests
import pyupbit
import pprint
from common_Import import *

'''
해당 파일은 업비트의 OpenAPI를 다루기 전 기본과정을 소개하는 파일입니다

[pyupbit에 대한 기본적 정보]
1. 모든 시세 조회(분봉, 일봉, 주봉)는 오전9시를 기준으로 초기화됩니다
2. 간단한 가격조회와 같은 기능은 OpenAPI 키를 발급받지 않아도 가능하지만, 주문진행 및 입출금을 위해선 발급을 받아하니 유의해주세요
3. 가격 조회의 기능은 py파일의 실행 시점을 기준으로 최대 200개의 행만 제공됩니다

[용어에 대한 설명 도움]
분봉 : 분단위
일봉 : 일단위
주봉 : 주단위
월봉 : 월단위

매수 : 구매행위
매도 : 판매행위

호가 정보 : 특정 종목에 대해 입력된 주문 정보
1호가 : 매도/매수의 첫번째 호가
2호가 : 매도/매수의 두번째 호가
1호가 > 2호가 > 3호가 > 4호가 > ... > N호가

<UPBIT API 등록>

1. cmd창 or 아나콘다 프롬프트에 아래 명령어 실행
ipconfig/all 

2. IPv4 주소 값 확인 (IP주소를 업비트 API 키 발급에 사용해야함)

3. 위 방식 외에도 네이버 "내 ip주소 조회" 검색을 통해서도 확인 가능

'''

# --------------------------------------------------------------------------------------------------------------------------
# 상장 종목 확인(KRW기준)
url = "https://api.upbit.com/v1/market/all"
resp = requests.get(url)
data = resp.json()

krw_tickers = []

for coin in data:
    ticker = coin['market']
    
    if ticker.startswith("KRW"):
        krw_tickers.append(ticker)
print(krw_tickers)

# --------------------------------------------------------------------------------------------------------------------------
# 분봉 조회
minute = 1 # 1, 3, 5, 10, 15, 30, 60, 240
num_count = 1000
df = pyupbit.get_ohlcv("KRW-BTC", f"minute{minute}", count=num_count)
print(df)

# 일봉 조회
df = pyupbit.get_ohlcv("KRW-BTC", interval='day', count=num_count)
print(df)

# 주봉 조회
df = pyupbit.get_ohlcv("KRW-BTC", interval='week')
print(df)

# --------------------------------------------------------------------------------------------------------------------------
# 현재 가격 조회 (py파일 실행 시점 당시 기준가격)
price = pyupbit.get_current_price("KRW-BTC")
print(price)

# 여러 종목 현재가 동시 조회
tickers = ['KRW-BTC', 'KRW-ETH']
price = pyupbit.get_current_price(tickers)
print(price)

# --------------------------------------------------------------------------------------------------------------------------
# 호가 정보 조회하기
orderbooks = pyupbit.get_orderbook("KRW-BTC")
pprint.pprint(orderbooks)

# --------------------------------------------------------------------------------------------------------------------------
# 업비트 API 로그인
f = open('./upbit_login.txt')
lines = f.readlines()

access_key = lines[0].strip()
secret_key = lines[1].strip()

f.close()

print(f'Access key 확인 : {access_key}')
print(f'Secret key 확인 : {secret_key}')
upbit = pyupbit.Upbit(access_key, secret_key) #업비트 본인 계좌 정보 객체를 생성합니다.
# --------------------------------------------------------------------------------------------------------------------------
# 업비트 잔고 정보 조회
balance = upbit.get_balances() # 현재 본인의 계좌 정보(원화를 포함한 모든 보유종목 정보)를 모두 가져옵니다.
print(balance)
print(balance[0]) # balance : 주문가능 금액/수량, locked : 현재 주문이 입력되어 호가창에 묶여있는 금액/수량, avg_buy_price : 매수평단가, avg_buy_price_modified : 매수평단가 수정 여부, unit_currency : 조회 종목의 구매기준 화폐

balance = upbit.get_balance("KRW") # 원화를 사용한 현재 본인의 주문가능한 금액/수량을 의미합니다(내부 값은 본인의 보유상품에 한 해서 수동으로 변경이 가능합니다.)
print(balance)

# --------------------------------------------------------------------------------------------------------------------------
# 지정가 매수주문 (해당 부분은 실행을 생략하겠습니다. 예시 설명을 위해서 제 계좌를 사용해 임시로 실행 결과를 확인해봤습니다)
# resp = upbit.buy_limit_order('KRW-XRP', 200, 100) # buy_limit_order(종목, 지정가격, 주문수량)은 실행과 즉시 주문이 입력됩니 주의하세요
# pprint.pprint(resp) 
'''
위와 같이 주문을 입력하고, 주문에 대한 정보를 조회하면 아래와 같은 결과가 생깁니다.

{'created_at': '2024-08-11T16:01:07+09:00', # 주문이 생성된 시간정보 입니다
 'executed_volume': '0',
 'locked': '20010',
 'market': 'KRW-XRP',
 'ord_type': 'limit', # limit은 지정가 주문을 했음을 의미하고, 우리는 리스크 부담을 줄이기 위해서 시장가 주문은 하지 않겠습니다
 'paid_fee': '0', # 이미 체결이 진행되어 지불한 수수료를 의미합니다
 'price': '200', # 진입 가격 수준입니다
 'remaining_fee': '10', # 주문이 체결되면 예상될 수수료를 의미합니다
 'remaining_volume': '100', # 아직 체결되지 않고 남은 수량을 의미합니다
 'reserved_fee': '10',
 'side': 'bid',
 'state': 'wait',
 'trades_count': 0,
 'uuid': 'd0d1bbbb-84b4-4b37-a137-90dddca15746', # 현재 주문에 대한 고유ID입니다. 해당 ID를 이용해 이후에 cancle_order함수를 사용해서 특정 주문을 취소할 수 있습니다
 'volume': '100'}

우리는 트레이딩 시스템에서 주문 이후에 특정 조건을 생성하거나, 주문을 취소하는 등의 과정을 수행하기 위해서 resp와 같은 변수에 주문 정보 객체를 지정하여 사용합니다

'''

# 시장가 매수주문 (해당 부분 또한 실행은 생략합니다.)
# resp = upbit.buy_market_order('KRW-XRP', 10000) # buy_market_order(종목, 주문가격)은 실행과 즉시 주문이 입력됩니 주의하세요

# 주문 취소
# upbit.cancel_order(uuid = resp['uuid']) 위와 같이 지정가 주문에서 resp와 같은 변수에 주문 정보를 입력할 경우 딕셔너리 상에서 주문 정보에 대한 고유ID를 사용해 주문을 취소할 수 있습니다


# --------------------------------------------------------------------------------------------------------------------------
''' # 업비트 잔고 정보 조회
def check_ticker_price(self):
    print("\n----BTC 금액 확인----\n")
    
    while True:
        now = datetime.datetime.now()
        price = pyupbit.get_current_price(self.target_ticker)
        
        print(now, price)
        time.sleep(1)

def check_ticker_price_df(self):
    print("\n----BTC 금액 확인----\n")
    
    while True:
        BTC_df = pyupbit.get_ohlcv("KRW-BTC", f"minute{self.minute}", count=self.num_count)
        print(BTC_df)
        time.sleep(1) '''