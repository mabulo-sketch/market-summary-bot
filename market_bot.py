"""
Bot de resumen de mercado.
Manda por Telegram cada hora: precio y variación de BTC/ETH/SOL,
precio de la acción de Ripley + IPSA, dólar observado, y el
Fear & Greed Index cripto.
Pensado para correr vía GitHub Actions (cron).
"""

import os
import requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

CRYPTO_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def get_crypto_data(symbol: str) -> dict:
    """Precio actual, variación 24h y volumen 24h desde Binance."""
    # Se usa data-api.binance.vision en vez de api.binance.com porque este
    # endpoint es solo de datos públicos y no aplica el geo-bloqueo (error 451)
    # que sí aplica el dominio principal a IPs de EE.UU. (como las de GitHub Actions).
    url = "https://data-api.binance.vision/api/v3/ticker/24hr"
    response = requests.get(url, params={"symbol": symbol}, timeout=15)
    response.raise_for_status()
    data = response.json()
    return {
        "symbol": symbol.replace("USDT", ""),
        "price": float(data["lastPrice"]),
        "change_pct": float(data["priceChangePercent"]),
        "volume": float(data["quoteVolume"]),  # volumen en USDT
    }


def get_yahoo_quote(ticker: str) -> dict:
    """Precio y variación desde Yahoo Finance (sirve para acciones chilenas e índices)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    result = response.json()["chart"]["result"][0]
    meta = result["meta"]
    price = meta["regularMarketPrice"]
    prev_close = meta["previousClose"]
    change_pct = ((price - prev_close) / prev_close) * 100
    return {"price": price, "change_pct": change_pct}


def get_usd_clp() -> float:
    """Dólar observado desde la API oficial chilena mindicador.cl"""
    url = "https://mindicador.cl/api/dolar"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    data = response.json()
    return data["serie"][0]["valor"]


def get_fear_greed() -> dict:
    """Índice de miedo y codicia del mercado cripto."""
    url = "https://api.alternative.me/fng/"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    data = response.json()["data"][0]
    return {"value": data["value"], "label": data["value_classification"]}


def format_number(n: float) -> str:
    return f"{n:,.2f}"


def format_volume(v: float) -> str:
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    return f"{v:,.0f}"


def build_message() -> str:
    lines = ["📊 <b>Resumen de mercado</b>\n"]

    # Cripto
    lines.append("<b>Cripto</b>")
    for symbol in CRYPTO_SYMBOLS:
        try:
            d = get_crypto_data(symbol)
            arrow = "🟢" if d["change_pct"] >= 0 else "🔴"
            lines.append(
                f"{arrow} {d['symbol']}: ${format_number(d['price'])} "
                f"({d['change_pct']:+.2f}% 24h, vol ${format_volume(d['volume'])})"
            )
        except Exception as e:
            lines.append(f"⚠️ {symbol}: error obteniendo datos ({e})")

    # Fear & Greed
    try:
        fg = get_fear_greed()
        lines.append(f"\n😨😏 Fear & Greed Index: {fg['value']} ({fg['label']})")
    except Exception as e:
        lines.append(f"\n⚠️ Fear & Greed: error ({e})")

    # Ripley + IPSA
    lines.append("\n<b>Chile</b>")
    try:
        ripley = get_yahoo_quote("RIPLEY.SN")
        arrow = "🟢" if ripley["change_pct"] >= 0 else "🔴"
        lines.append(f"{arrow} Ripley: ${format_number(ripley['price'])} CLP ({ripley['change_pct']:+.2f}%)")
    except Exception as e:
        lines.append(f"⚠️ Ripley: error obteniendo datos ({e})")

    try:
        ipsa = get_yahoo_quote("^IPSA")
        arrow = "🟢" if ipsa["change_pct"] >= 0 else "🔴"
        lines.append(f"{arrow} IPSA: {format_number(ipsa['price'])} pts ({ipsa['change_pct']:+.2f}%)")
    except Exception as e:
        lines.append(f"⚠️ IPSA: error obteniendo datos ({e})")

    try:
        usd_clp = get_usd_clp()
        lines.append(f"💵 Dólar observado: ${format_number(usd_clp)} CLP")
    except Exception as e:
        lines.append(f"⚠️ Dólar: error obteniendo datos ({e})")

    return "\n".join(lines)


def send_telegram_message(text: str) -> None:
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    response = requests.post(TELEGRAM_API_URL, data=payload, timeout=15)
    response.raise_for_status()


def main():
    mensaje = build_message()
    print(mensaje)
    send_telegram_message(mensaje)


if __name__ == "__main__":
    main()
