# main.py – Bot Trading Scalping Otomatis untuk Bybit
import time, requests, hmac, hashlib, json
from datetime import datetime
import os

# Load API dari Environment Variable
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

TP_PCT = 3.2 / 100  # 3.2%
SL_PCT = 2.5 / 100  # 2.5%
FEE_PCT = 0.2 / 100  # 0.2%
TRADE_USDT = 10  # jumlah tetap per trade

positions = {}
price_log = {}
log_profit = []

COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "INJUSDT", "ARBUSDT", "OPUSDT"]

# === Telegram Notifikasi ===
def send_tele(msg):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TG_CHAT_ID, "text": msg})
    except:
        pass

# === Ambil harga real-time ===
def get_price(symbol):
    url = f"https://api.bybit.com/v5/market/tickers?category=spot"
    r = requests.get(url).json()
    for i in r['result']['list']:
        if i['symbol'] == symbol:
            return float(i['lastPrice'])
    return None

# === Hitung RSI sederhana ===
def calc_rsi(prices):
    if len(prices) < 15:
        return 50
    gain, loss = [], []
    for i in range(-14, -1):
        d = prices[i+1] - prices[i]
        (gain if d > 0 else loss).append(abs(d))
    avg_gain = sum(gain)/14 if gain else 0.01
    avg_loss = sum(loss)/14 if loss else 0.01
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

# === Buat Signature Bybit ===
def make_signature(payload):
    q = '&'.join([f"{k}={payload[k]}" for k in sorted(payload)])
    return hmac.new(API_SECRET.encode(), q.encode(), hashlib.sha256).hexdigest()

# === Order Market Buy/Sell ===
def order_market(symbol, qty, side):
    ts = str(int(time.time() * 1000))
    payload = {
        "category": "spot",
        "symbol": symbol,
        "side": side,
        "orderType": "Market",
        "qty": str(qty),
        "timestamp": ts,
        "apiKey": API_KEY
    }
    sig = make_signature(payload)
    headers = {
        "Content-Type": "application/json",
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-SIGN": sig,
        "X-BAPI-TIMESTAMP": ts
    }
    r = requests.post("https://api.bybit.com/v5/order/create", headers=headers, data=json.dumps(payload))
    return r.json()

# === Loop Utama ===
price_hist = {s: [] for s in COINS}
while True:
    for sym in COINS:
        price = get_price(sym)
        if not price:
            continue

        price_hist[sym].append(price)
        if len(price_hist[sym]) > 20:
            price_hist[sym].pop(0)

        rsi = calc_rsi(price_hist[sym])

        if sym in positions:
            pos = positions[sym]
            entry = pos['buy']
            qty = pos['qty']
            if price >= entry * (1 + TP_PCT):
                order_market(sym, qty, "Sell")
                profit = (price - entry) * qty
                fee = (price + entry) * qty * FEE_PCT
                net = profit - fee
                send_tele(f"SELL {sym}\nEntry: {entry}\nExit: {price}\nNet: ${round(net, 2)}")
                del positions[sym]
            elif price <= entry * (1 - SL_PCT):
                order_market(sym, qty, "Sell")
                loss = (price - entry) * qty
                fee = (price + entry) * qty * FEE_PCT
                net = loss - fee
                send_tele(f"STOP LOSS {sym}\nEntry: {entry}\nExit: {price}\nNet: ${round(net, 2)}")
                del positions[sym]
        else:
            if rsi < 30:
                qty = round(TRADE_USDT / price, 4)
                res = order_market(sym, qty, "Buy")
                if res.get("retCode") == 0:
                    positions[sym] = {"buy": price, "qty": qty}
                    send_tele(f"BUY {sym}\nQty: {qty}\nPrice: {price} | RSI: {rsi}")

    time.sleep(60)
