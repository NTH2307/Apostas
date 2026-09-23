"""Envio de alertas por Telegram."""
import requests

import config


def enviar_alerta(mensagem: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print(f"[alerta, Telegram não configurado] {mensagem}")
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resposta = requests.post(
            url,
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": mensagem},
            timeout=10,
        )
        resposta.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Falha ao enviar alerta Telegram: {e}")
        return False
