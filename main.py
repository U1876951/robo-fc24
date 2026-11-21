from flask import Flask
import threading
import os
import telebot
import math
import random
from collections import Counter

app = Flask('')

@app.route('/')
def home():
    return "Robô online!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

threading.Thread(target=run).start()

# ⚠️ COLOQUE O SEU NOVO TOKEN AQUI ⚠️
TOKEN = "9114122727:AAFdZY2ESyDfHD1njhkWjRCg26jPV9Eoy8M" 
bot = telebot.TeleBot(TOKEN)

N_SIMULACOES = 20000

def calcular_probabilidades_implicitas(odds):
    brutas = {k: 1.0 / v for k, v in odds.items() if v > 1.0}
    total = sum(brutas.values())
    justas = {k: p / total for k, p in brutas.items()}
    return justas, total - 1.0

def simular(lam_h, lam_a):
    over = 0
    placares = Counter()
    for _ in range(N_SIMULACOES):
        gh, ga = 0, 0
        L_h, L_a = math.exp(-lam_h), math.exp(-lam_a)
        p_h, p_a = 1.0, 1.0
        
        while True:
            p_h *= random.random()
            if p_h <= L_h: break
            gh += 1
            
        while True:
            p_a *= random.random()
            if p_a <= L_a: break
            ga += 1
            
        placares[(gh, ga)] += 1
        if gh + ga > 14.5: over += 1
    return placares, over / N_SIMULACOES

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    texto = (
        "🤖 *Olá! Sou o Robô FC 24.*\n\n"
        "Envie os dados separados por vírgula:\n"
        "`Casa, Visitante, OddCasa, OddEmpate, OddFora, OddOver, OddUnder`\n\n"
        "Exemplo:\n"
        "`Aston Villa, Fulham, 1.445, 9.57, 3.43, 2.025, 1.825`"
    )
    bot.reply_to(message, texto, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def processar(message):
    try:
        partes = message.text.replace(" ", "").split(",")
        if len(partes) != 7:
            bot.reply_to(message, "❌ Erro: Envie 7 dados separados por vírgula. Ex: TimeA, TimeB, 1.5, 4.0, 3.0, 1.9, 1.9")
            return

        time_h, time_a = partes[0], partes[1]
        odd_h, odd_d, odd_a = float(partes[2]), float(partes[3]), float(partes[4])
        odd_over, odd_under = float(partes[5]), float(partes[6])

        bot.reply_to(message, "⏳ Simulando 20.000 jogos...")

        justas, _ = calcular_probabilidades_implicitas({"home": odd_h, "draw": odd_d, "away": odd_a})
        
        p_empate = justas.get("draw", 0.25)
        lam_total = 14.0 + ((0.30 - p_empate) * 2.0)
        forca_h = justas["home"] + 0.5 * justas["draw"]
        forca_a = justas["away"] + 0.5 * justas["draw"]
        lam_h = lam_total * (forca_h / (forca_h + forca_a))
        lam_a = lam_total * (forca_a / (forca_h + forca_a))

        placares, p_over = simular(lam_h, lam_a)
        p_under = 1 - p_over
        
        ev_over = (p_over * odd_over - 1) * 100
        ev_under = (p_under * odd_under - 1) * 100

        top3 = sorted(placares.items(), key=lambda x: -x[1])[:3]
        res_placares = "".join([f"   {sh}-{sa} ({c/N_SIMULACOES*100:.1f}%)\n" for (sh, sa), c in top3])

        resposta = (
            f"⚽ *{time_h} vs {time_a}*\n\n"
            f"🎯 *Probabilidades 1X2:*\n"
            f"   Casa: {justas['home']*100:.1f}%\n"
            f"   Empate: {justas['draw']*100:.1f}%\n"
            f"   Fora: {justas['away']*100:.1f}%\n\n"
            f"📈 *Gols Esperados (λ):*\n"
            f"   {time_h}: {lam_h:.2f}\n"
            f"   {time_a}: {lam_a:.2f}\n"
            f"   Total: {lam_total:.2f}\n\n"
            f"🏆 *Top 3 Placares:*\n{res_placares}\n"
            f"🎲 *Over/Under 14.5:*\n"
            f"   P(Over): {p_over*100:.1f}%\n"
            f"   P(Under): {p_under*100:.1f}%\n\n"
            f"💡 *Value Bet:*\n"
            f"   OVER EV: {ev_over:+.1f}%\n"
            f"   UNDER EV: {ev_under:+.1f}%"
        )
        bot.reply_to(message, resposta, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, "❌ Erro nos dados. Verifique as vírgulas e os números.")

print("Bot online! Aguardando mensagens...")
bot.infinity_polling()
