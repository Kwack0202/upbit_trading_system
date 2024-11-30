from common_Import import *
from utils.Generate_plot_and_indicators import *
from utils.trend_combination import *

    # --------------------------------------------------------------------------------------------------------------------------------------------------------------------
def plot_candles(pricing, title=None, trend_line=False, mean_std_line=False, volume_bars=False, color_function=None, technicals=None, ax=None):
    
    def default_color(index, open_price, close_price, low, high):
        return 'b' if open_price[index] > close_price[index] else 'r'
    
    color_function = color_function or default_color
    technicals = technicals or []
    open_price = pricing['open']
    close_price = pricing['close']
    low = pricing['low']
    high = pricing['high']
    oc_min = pd.concat([open_price, close_price], axis=1).min(axis=1)
    oc_max = pd.concat([open_price, close_price], axis=1).max(axis=1)
    
    def plot_trendline(ax, pricing, linewidth=2):
        x = np.arange(len(pricing))
        y = pricing.values
        z = np.polyfit(x, y, 1)
        p = np.poly1d(z)
        ax.plot(x, p(x), 'g-', linewidth=linewidth)
    
    def plot_mean_std(ax, pricing, color='red', linewidth=2):
        data = pricing['close']
        mean = data.mean()
        std = data.std()
        x = np.arange(len(pricing))
        
        # 0.5 * 표준편차를 기준으로 진행
        ax.plot(x, [mean + std * 0.43] * len(pricing), color=color, linestyle='--', linewidth=linewidth)
        ax.plot(x, [mean - std * 0.43] * len(pricing), color=color, linestyle='--', linewidth=linewidth) 
    
    if volume_bars:
        if ax is None:
            fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, gridspec_kw={'height_ratios': [3,1]}, figsize=(20,10))
        else:
            ax1 = ax
            ax2 = ax.twinx()  # For volume bars
    else:
        if ax is None:
            fig, ax1 = plt.subplots(1, 1)
        else:
            ax1 = ax
    
    if title:
        ax1.set_title(title)
    
    x = np.arange(len(pricing))
    candle_colors = [color_function(i, open_price, close_price, low, high) for i in x]
    candles = ax1.bar(x, oc_max-oc_min, bottom=oc_min, color=candle_colors, linewidth=0)
    lines = ax1.vlines(x , low, high, color=candle_colors, linewidth=1)
    
    # 추세선 생성
    if trend_line:
        plot_trendline(ax1, pricing['close'])
    
    # 평균, 표준편차 라인 생성
    if mean_std_line:
        plot_mean_std(ax1, pricing)
    
    ax1.xaxis.grid(True)
    ax1.yaxis.grid(True)
    ax1.xaxis.set_tick_params(which='major', length=3.0, direction='in', top='off')
    ax1.set_xticklabels([])
    ax1.set_yticklabels([])
    ax1.xaxis.set_visible(False)
    ax1.yaxis.set_visible(False)
    ax1.axis(False)

    for indicator in technicals:
        ax1.plot(x, indicator)
    
    if volume_bars:
        volume = pricing['volume']
        volume_scale = None
        scaled_volume = volume
        
        if volume.max() > 1000000:
            volume_scale = 'M'
            scaled_volume = volume / 1000000
            
        elif volume.max() > 1000:
            volume_scale = 'K'
            scaled_volume = volume / 1000
            
        ax2.bar(x, scaled_volume, color=candle_colors)
        volume_title = 'volume'
        
        if volume_scale:
            volume_title = 'volume (%s)' % volume_scale
            
        ax2.set_yticklabels([])
        ax2.set_xticklabels([])
        ax2.axis(False)
        
    if ax is None and volume_bars:
        return fig, ax1, ax2
    elif ax is None:
        return fig, ax1
    else:
        return ax1  # When ax is provided, just return ax1


# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 기술적 지표 추가 부분
def generate_technical_analysis_indicators(df):
    '''    
    본인의 취향에 따라서 지표를 추가해서 사용하세요
    
    현재는 제 취향껏 지표를 추가했고, 각 값은 여러 증권사에서 흔히 사용하는 값으로 입력했습니다

    '''
    # 볼린저 밴드
    df['BBAND_UPPER'],df['BBAND_MIDDLE'],df['BBAND_lOWER'] = talib.BBANDS(df['close'], 20, 2)
    
    # 모멘텀
    df['MOM'] = talib.MOM(df["close"], timeperiod=10)
    
    # DMI
    #df['DMI'] = talib.DX(df["high"], df["low"], df["close"], timeperiod=14)
    
    # ROC
    #df['ROC'] = talib.ROC(df["close"], timeperiod=10)
    
    # ADX
    #df['ADX'] = talib.ADX(df["high"], df["low"], df["close"], timeperiod=14)
    
    # AROON Oscillator
    #df['AROON_OSC'] = talib.AROONOSC(df["high"], df["low"], timeperiod=14)
    
    # CCI
    #df['CCI'] = talib.CCI(df["high"], df["low"], df["close"], timeperiod=9)
    
    # RSI (원래는 14가 기본값으로 제공되지만 우리는 12로 사용함)
    df['RSI'] = talib.RSI(df["close"], timeperiod=12)
    
    # Stochastic
    #df['slowk'], df['slowd'] = talib.STOCH(df["high"], df["low"], df["close"], fastk_period=12, slowk_period=5, slowk_matype=0, slowd_period=5, slowd_matype=0)
    #df['fastk'], df['fastd'] = talib.STOCHF(df["high"], df["low"], df["close"], fastk_period=12, fastd_period=5, fastd_matype=0)
    
    # Chande Momentum Oscilator
    #df['CMO'] = talib.CMO(df["close"], timeperiod=9)
    
    # Percentage Price Oscillator
    #df['PPO'] = talib.PPO(df["close"], fastperiod=10, slowperiod=20, matype=0)
    
    # Ultimate Oscillator
    #df['UO'] = talib.ULTOSC(df["high"], df["low"], df["close"], timeperiod1=7, timeperiod2=14, timeperiod3=28)
    
    #df['BOP'] = talib.BOP(df['open'], df['high'], df['low'], df['close'])
    
    return df


# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 추세 판단 부분
def generate_trend(df):
    pricing = df['close']
    x = np.arange(len(pricing))
    y = pricing.values
    z = np.polyfit(x, y, 1)
    p = np.poly1d(z)
    
    # 평균 / 표준편차 생성
    mean_close = pricing.mean()
    std_close = pricing.std()
    
    # 상방, 하방 라인 생성
    upper_bound = mean_close + std_close * 0.43 
    lower_bound = mean_close - std_close * 0.43
    trend_point = z[0] * x[-1] + z[1]
    
    if trend_point > upper_bound:
        trend = 'up'
    elif lower_bound < trend_point < upper_bound:
        trend = 'sideway'
    else:
        trend = 'down'
        
    return trend

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 단~장기 추세를 종합한 최종 추세
def determine_final_trend(trend_results, trend_combinations):
    # 기간별 추세를 추출
    long_trend = trend_results[1].split(": ")[1]  # Long Period
    medium_trend = trend_results[2].split(": ")[1]  # Medium Period
    short_trend = trend_results[3].split(": ")[1]  # Short Period
    
    # 최종 추세 결정
    final_trend = trend_combinations.get((long_trend, medium_trend, short_trend), "unknown")
    
    return final_trend

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# MOM의 추세를 분석하는 함수 정의
def analyze_mom_trend(mom_values):
    if mom_values.empty:
        return None
    
    mean_mom = mom_values.mean()
    ''' std_mom = mom_values.std()
    
    upper_bound = mean_mom + std_mom * 0.43
    lower_bound = mean_mom - std_mom * 0.43 '''
    last_mom_value = mom_values.iloc[-1]
    
    if last_mom_value > mean_mom:
        trend = 'up'
    else:
        trend = 'down'
    
    return trend

# 데이터프레임에 새로운 MOM 트렌드 컬럼 추가
def add_mom_trend_column(df, window_len):
    mom_trends = []
    end_date = (pd.Timestamp('today') + pd.Timedelta(days=1)).date()
    
    for i in range(len(df)):
        # 인덱스에서 날짜를 가져오기
        current_date = df.index[i].date()

        # 마지막 날짜 이후 데이터는 계산하지 않음
        if current_date >= end_date:
            mom_trends.append(None)
            continue

        if i >= window_len-1:
            subset_mom = df.iloc[i-window_len-1:i+1]['MOM']
            mom_trend = analyze_mom_trend(subset_mom)
            mom_trends.append(mom_trend)
        else:
            mom_trends.append(None)
        
    df[f'mom_trend'] = mom_trends
    return df