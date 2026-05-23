import os
import requests
import yfinance as yf
import pandas as pd

BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

def get_close(ticker, period="300d"):
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df['Close'].dropna()

def calc_signal():
    tqqq  = get_close("TQQQ")
    qqq   = get_close("QQQ")
    spy   = get_close("SPY")
    vix   = get_close("^VIX")
    dxy   = get_close("DX-Y.NYB")
    us10y = get_close("^TNX")
    us2y  = get_close("^IRX")

    t_c     = float(tqqq.iloc[-1])
    t_p     = float(tqqq.iloc[-2])
    t_ma200 = float(tqqq.rolling(200).mean().iloc[-1])
    t_v20   = float(tqqq.pct_change().rolling(20).std().iloc[-1])
    dist200 = (t_c / t_ma200) * 100.0

    q_close = float(qqq.iloc[-1])
    q_ma3   = float(qqq.rolling(3).mean().iloc[-1])
    q_ma161 = float(qqq.rolling(161).mean().iloc[-1])

    s_c     = float(spy.iloc[-1])
    s_ma200 = float(spy.rolling(200).mean().iloc[-1])
    spy_dist200 = (s_c / s_ma200) * 100.0

    vix_c = float(vix.iloc[-1])

    dxy_c   = float(dxy.iloc[-1])
    dxy_ref = float(dxy.iloc[-121]) if len(dxy) >= 121 else float(dxy.iloc[0])
    dxy_roc = ((dxy_c / dxy_ref) - 1.0) * 100.0

    us10y_c   = float(us10y.iloc[-1])
    us10y_ref = float(us10y.iloc[-61]) if len(us10y) >= 61 else float(us10y.iloc[0])
    us10y_chg = us10y_c - us10y_ref

    us2y_c   = float(us2y.iloc[-1])
    us2y_ref = float(us2y.iloc[-81]) if len(us2y) >= 81 else float(us2y.iloc[0])
    us2y_chg = us2y_c - us2y_ref

    vol_thr  = 0.059
    locked   = t_v20 >= vol_thr
    above200 = dist200 >= 102.27
    qbull    = q_ma3 > q_ma161
    spy_bear = spy_dist200 <= 96.80
    vix_risk = vix_c >= 46.0

    t3_qweak    = q_close < q_ma3
    t3_dxy_risk = dxy_roc > 0.0
    t3_10y_risk = us10y_chg > 0.40
    t3_2y_risk  = us2y_chg > 0.50
    t3_risk_zero = t3_qweak and ((t3_dxy_risk and t3_10y_risk) or t3_2y_risk)
    t3_cap = t3_qweak and not t3_risk_zero

    if locked or spy_bear or vix_risk:
        base_weight = 0.0
    elif above200 and qbull:
        base_weight = 1.0
    elif qbull:
        base_weight = 0.20
    else:
        base_weight = 0.0

    if t3_risk_zero:
        final_weight = 0.0
    elif t3_cap and base_weight > 0.80:
        final_weight = 0.80
    else:
        final_weight = base_weight

    if dist200 >= 153.0:
        final_weight = 0.0
    elif dist200 >= 147.0 and final_weight > 0.05:
        final_weight = 0.05
    elif dist200 >= 144.0 and final_weight > 0.80:
        final_weight = 0.80
    elif dist200 >= 140.0 and final_weight > 0.90:
        final_weight = 0.90

    def weight_to_str(w):
        if w <= 0: return "현금(SGOV)"
        return f"TQQQ({int(w*100)}%)"

    def ri(is_risk):
        return "🔴" if is_risk else "🟢"

    chg_pct = ((t_c / t_p) - 1.0) * 100.0
    pos_str = weight_to_str(final_weight)

    msg = f"""📊 <b>김째매매법 일일현황</b>

<b>목표 포지션: {pos_str}</b>

----------------------------------------
📈 시장 데이터
TQQQ: {t_c:.4f} ({chg_pct:+.2f}%)
200일 이동평균: {t_ma200:.4f}
200일 이격도: {dist200:.2f}%
20일 변동성: {t_v20*100:.2f}% {ri(locked)}

SPY 200일 필터: {spy_dist200:.2f}% {ri(spy_bear)}
VIX: {vix_c:.2f} {ri(vix_risk)}

T3D80: {"강한위험(현금) 🔴" if t3_risk_zero else "80%cap 🔴" if t3_cap else "정상 🟢"}
DXY 120D: {dxy_roc:+.2f}% {ri(t3_dxy_risk)}
10Y 60D: {us10y_chg:+.2f}%p {ri(t3_10y_risk)}
2Y 80D: {us2y_chg:+.2f}%p {ri(t3_2y_risk)}
QQQ 3일선: {"약세 🔴" if t3_qweak else "정상 🟢"}"""

    send_telegram(msg)

if __name__ == "__main__":
    calc_signal()
