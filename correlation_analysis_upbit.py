import time
import requests
import pandas as pd
from market_data_pool import MarketDataPool
import sys
print("✅ 현재 Python 실행 경로:", sys.executable)


# === 설정 ===
INTERVAL = 0.25  # 업비트 API 요청 간격 (초)
CANDLE_COUNT = 60  # 가져올 캔들 개수
CORRELATION_THRESHOLD = 0.85  # 상관계수 커플 기준
CSV_FILENAME = "ha_correlation_pairs.csv"

# === 캔들 데이터 수집 ===
def fetch_closes(symbol, count=CANDLE_COUNT):
    url = f"https://api.upbit.com/v1/candles/minutes/5?market={symbol}&count={count}"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            df = pd.DataFrame(res.json())
            df = df[['candle_date_time_kst', 'trade_price']].rename(columns={'trade_price': symbol})
            df['candle_date_time_kst'] = pd.to_datetime(df['candle_date_time_kst'])
            df = df.sort_values('candle_date_time_kst').reset_index(drop=True)
            return df[[symbol]]
    except Exception as e:
        print(f"❌ {symbol} 데이터 수집 실패: {e}")
    return pd.DataFrame()

# === 상관관계 분석 및 저장 ===
def build_correlation_csv(symbols, filename=CSV_FILENAME):
    price_df = pd.DataFrame()
    for symbol in symbols:
        df = fetch_closes(symbol)
        if not df.empty:
            price_df = pd.concat([price_df, df], axis=1)
        time.sleep(INTERVAL)  # API rate limit 대응

    returns = price_df.pct_change().dropna()
    corr = returns.corr()

    pairs = []
    for i in range(len(corr.columns)):
        for j in range(i+1, len(corr.columns)):
            val = corr.iloc[i, j]
            if val >= CORRELATION_THRESHOLD:
                pairs.append([corr.index[i], corr.columns[j], round(val, 3)])

    result = pd.DataFrame(pairs, columns=["Symbol A", "Symbol B", "Correlation"])
    result.to_csv(filename, index=False)
    print(f"✅ CSV 저장 완료: {filename}")

# === 실행 진입점 ===
if __name__ == "__main__":
    print("🚀 상관관계 분석 시작")
    pool = MarketDataPool(mode='A')
    watchlist = pool.get_top_symbols()
    print(f"🔍 감시 종목 수: {len(watchlist)}")
    build_correlation_csv(watchlist)
    print("🎯 분석 완료")
