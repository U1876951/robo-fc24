import os
import time
import math
import random
import logging
import threading
from collections import Counter

from flask import Flask
import telebot

# CONFIGURAÇÃO
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

if not TOKEN:
    raise RuntimeError(
        "Falta configurar TELEGRAM_BOT_TOKEN no Render."
    )

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

N_SIMULACOES = 20000


@app.route("/")
def home():
    return "Robô FC 24 online! 🤖⚽", 200


def calcular_probabilidades_implicitas(odds):
    if any(odd <= 1.0 for odd in odds.values()):
        raise ValueError("As odds devem ser superiores a 1.00.")

    brutas = {k: 1.0 / v for k, v in odds.items()}
    total = sum(brutas.values())

    justas = {
        k: valor / total
        for k, valor in brutas.items()
    }

    margem = (total - 1.0) * 100
    return justas, margem


def sortear_poisson(lam):
    limite = math.exp(-lam)
    produto = 1.0
    golos = 0

    while produto > limite:
        produto *= random.random()
        if produto > limite:
            golos += 1

    return golos


def simular(lam_casa, lam_fora):
    placares = Counter()
    over = 0

    for _ in range(N_SIMULACOES):
        casa = sortear_poisson(lam_casa)
        fora = sortear_poisson(lam_fora)

        placares[(casa, fora)] += 1

        if casa + fora >= 15:
            over += 1

    return placares, over / N_SIMULACOES


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):

    texto = (
        "🤖 *Olá! Sou o Robô FC 24.*\n\n"
        "Envie os dados separados por vírgulas:\n\n"
        "`Casa, Visitante, OddCasa, OddEmpate, "
        "OddFora, OddOver, OddUnder`\n\n"
        "Exemplo:\n"
        "`Aston Villa, Fulham, 1.445, 4.57, "
        "3.43, 2.025, 1.825`\n\n"
        "⚽ Estou pronto para analisar!"
    )

    bot.reply_to(message, texto, parse_mode="Markdown")


@bot.message_handler(func=lambda message: bool(message.text))
def processar(message):

    try:
        partes = [
            parte.strip()
            for parte in message.text.split(",")
        ]

        if len(partes) != 7:
            bot.reply_to(
                message,
                "❌ Envie exatamente 7 dados separados por vírgulas."
            )
            return

        time_casa = partes[0]
        time_fora = partes[1]

        if not time_casa or not time_fora:
            raise ValueError("Indique os nomes das equipas.")

        odd_casa, odd_empate, odd_fora, odd_over, odd_under = (
            map(float, partes[2:])
        )

        odds = {
            "home": odd_casa,
            "draw": odd_empate,
            "away": odd_fora
        }

        justas, margem = calcular_probabilidades_implicitas(odds)

        if odd_over <= 1 or odd_under <= 1:
            raise ValueError("Odds Over/Under inválidas.")

        bot.reply_to(
            message,
            "⏳ A simular 20.000 jogos..."
        )

        # MODELO DE SIMULAÇÃO

        p_empate = justas["draw"]

        lam_total = 14.0 + (
            (0.30 - p_empate) * 2.0
        )

        lam_total = max(8.0, min(20.0, lam_total))

        forca_casa = (
            justas["home"] + 0.5 * justas["draw"]
        )

        forca_fora = (
            justas["away"] + 0.5 * justas["draw"]
        )

        soma = forca_casa + forca_fora

        lam_casa = lam_total * forca_casa / soma
        lam_fora = lam_total * forca_fora / soma

        placares, p_over = simular(
            lam_casa,
            lam_fora
        )

        p_under = 1 - p_over

        ev_over = (
            p_over * odd_over - 1
        ) * 100

        ev_under = (
            p_under * odd_under - 1
        ) * 100

        top3 = sorted(
            placares.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        res_placares = ""

        for (casa, fora), quantidade in top3:

            percentagem = (
                quantidade / N_SIMULACOES
            ) * 100

            res_placares += (
                f"   {casa}-{fora} "
                f"({percentagem:.1f}%)\n"
            )

        resposta = (
            f"⚽ *{time_casa} vs {time_fora}*\n\n"

            f"🎯 *PROBABILIDADES 1X2*\n"
            f"Casa: {justas['home']*100:.1f}%\n"
            f"Empate: {justas['draw']*100:.1f}%\n"
            f"Fora: {justas['away']*100:.1f}%\n"
            f"Margem das odds: {margem:.1f}%\n\n"

            f"📈 *GOLOS ESPERADOS*\n"
            f"{time_casa}: {lam_casa:.2f}\n"
            f"{time_fora}: {lam_fora:.2f}\n"
            f"Total: {lam_total:.2f}\n\n"

            f"🏆 *TOP 3 PLACARES*\n"
            f"{res_placares}\n"

            f"🎲 *OVER / UNDER 14.5*\n"
            f"Over: {p_over*100:.1f}%\n"
            f"Under: {p_under*100:.1f}%\n\n"

            f"💎 *VALUE BET (+EV)*\n"
            f"Over EV: {ev_over:+.1f}%\n"
            f"Under EV: {ev_under:+.1f}%\n\n"

            "ℹ️ Simulação matemática baseada nas odds "
            "fornecidas. Não utiliza estatísticas reais "
            "nem dados ao vivo. EV positivo não garante lucro."
        )

        bot.reply_to(
            message,
            resposta,
            parse_mode="Markdown"
        )

    except ValueError as erro:

        bot.reply_to(
            message,
            f"❌ Dados inválidos: {erro}"
        )

    except Exception:

        logging.exception("Erro ao processar mensagem")

        bot.reply_to(
            message,
            "❌ Ocorreu um erro. Tente novamente."
        )


def iniciar_bot():

    while True:

        try:

            logging.info("A iniciar o Telegram...")

            bot.infinity_polling(
                skip_pending=True,
                timeout=20,
                long_polling_timeout=20
            )

        except Exception:

            logging.exception(
                "Erro no Telegram. Nova tentativa em 5 segundos."
            )

            time.sleep(5)


if __name__ == "__main__":

    threading.Thread(
        target=iniciar_bot,
        daemon=True
    ).start()

    porta = int(os.environ.get("PORT", "10000"))

    logging.info("Robô FC 24 a iniciar...")

    app.run(
        host="0.0.0.0",
        port=porta
        )
