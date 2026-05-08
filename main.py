import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import time

# --- KONFIGURACE ---
SYMBOL = "XAUUSD"
TF_ENTRY = mt5.TIMEFRAME_M15
TF_TREND = mt5.TIMEFRAME_H1

def get_data(symbol, timeframe, count=200):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def find_order_block(df):
    """Zjednodušená detekce Order Blocku na základě Volume a ceny"""
    last_candle = df.iloc[-2]
    prev_candle = df.iloc[-3]
    avg_volume = df['tick_volume'].tail(20).mean()
    
    # Bullish Order Block (Poslední prodejní svíčka před masivním nákupem)
    if last_candle['close'] > last_candle['open'] and last_candle['tick_volume'] > avg_volume * 1.5:
        if prev_candle['close'] < prev_candle['open']:
            return "BULLISH_OB", prev_candle['low']
            
    # Bearish Order Block (Poslední nákupní svíčka před masivním výprodejem)
    if last_candle['close'] < last_candle['open'] and last_candle['tick_volume'] > avg_volume * 1.5:
        if prev_candle['close'] > prev_candle['open']:
            return "BEARISH_OB", prev_candle['high']
            
    return None, None

def analyze():
    # Načtení dat
    df_h1 = get_data(SYMBOL, TF_TREND, 250)
    df_m15 = get_data(SYMBOL, TF_ENTRY, 100)

    # Indikátory H1 (Trend)
    ema_200_h1 = ta.ema(df_h1['close'], length=200).iloc[-1]
    
    # Indikátory M15 (Vstup)
    df_m15['ema20'] = ta.ema(df_m15['close'], length=20)
    df_m15['ema50'] = ta.ema(df_m15['close'], length=50)
    df_m15['rsi'] = ta.rsi(df_m15['close'], length=14)
    macd = ta.macd(df_m15['close'])
    df_m15 = pd.concat([df_m15, macd], axis=1)
    
    # Aktuální hodnoty
    price = mt5.symbol_info_tick(SYMBOL).bid
    rsi = df_m15['rsi'].iloc[-1]
    macd_main = df_m15['MACD_12_26_9'].iloc[-1]
    macd_sig = df_m15['MACDs_12_26_9'].iloc[-1]
    ob_type, ob_level = find_order_block(df_m15)
    
    # Logika vstupu
    signal = "NEUTRAL"
    sl, tp = 0, 0

    # PODMÍNKY PRO LONG
    # 1. Cena > EMA 200 (H1)
    # 2. EMA 20 > EMA 50 (M15)
    # 3. RSI < 60 (nejsme extrémně překoupení)
    # 4. MACD Cross (Main > Signal)
    if price > ema_200_h1 and df_m15['ema20'].iloc[-1] > df_m15['ema50'].iloc[-1]:
        if macd_main > macd_sig and rsi > 50:
            signal = "LONG / BUY"
            # SL pod poslední Order Block nebo EMA 50
            sl = ob_level if ob_type == "BULLISH_OB" else df_m15['ema50'].iloc[-1]
            tp = price + (price - sl) * 2.5 # RRR 1:2.5

    # PODMÍNKY PRO SHORT
    elif price < ema_200_h1 and df_m15['ema20'].iloc[-1] < df_m15['ema50'].iloc[-1]:
        if macd_main < macd_sig and rsi < 50:
            signal = "SHORT / SELL"
            sl = ob_level if ob_type == "BEARISH_OB" else df_m15['ema50'].iloc[-1]
            tp = price - (sl - price) * 2.5

    return signal, price, sl, tp

# --- ENGINE ---
if not mt5.initialize():
    quit()

print("Programátor Zlata: Systém aktivní...")

try:
    while True:
        sig, p, sl, tp = analyze()
        if sig != "NEUTRAL":
            print(f"\n[!] SIGNÁL: {sig}")
            print(f"Vstup: {p:.2f} | SL: {sl:.2f} | TP: {tp:.2f}")
            print(f"Risk/Reward: 1:2.5")
            print("-" * 30)
        time.sleep(30) # Analýza každých 30 sekund
except KeyboardInterrupt:
    mt5.shutdown()
