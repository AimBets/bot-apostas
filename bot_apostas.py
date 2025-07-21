import re
import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# === CONFIGURAÇÕES ===
TOKEN = '8122331285:AAGch9pES6JyoEtpVrjrwHiyRHJZxK5tNWI'
DESTINO_CHAT_ID = -1002540984437  # ID do canal destino

# === BANCO DE DADOS LOCAL ===
conn = sqlite3.connect('mensagens.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS mensagens (
        origem_msg_id INTEGER PRIMARY KEY,
        destino_msg_id INTEGER
    )
''')
conn.commit()

# === FUNÇÕES AUXILIARES ===
def identificar_esporte(texto):
    if re.search(r'\(Q[1-4]\)', texto):
        return "🏀 Ebasketball"
    return "⚽️ Fifa"

def extrair_dados(mensagem):
    esporte = identificar_esporte(mensagem)
    linha_odd = re.search(r'🏆 (.+?@\d+\.\d+)', mensagem)
    confronto = re.search(r'@[\d\.]+ - (.+? vs .+?) -', mensagem)
    placar = re.search(r'🔢 (\d+x\d+)', mensagem)
    tempo = re.search(r'🕒 (\d{2}:\d{2})', mensagem)
    status = re.search(r'Status da Aposta: (✅ Green|❌ Red|🟩 Half_green|🟥 Half_red|⚪ Void)', mensagem)
    link = re.search(r'(https:\/\/www\.bet365\.com\/dl\/sportsbookredirect\?[^ \n]+)', mensagem)

    return {
        "esporte": esporte,
        "linha_odd": linha_odd.group(1) if linha_odd else "",
        "confronto": confronto.group(1).strip() if confronto else "",
        "placar": placar.group(1) if placar else "",
        "tempo": tempo.group(1) if tempo else "",
        "status": status.group(1) if status else "",
        "link": link.group(1) if link else ""
    }

def formatar_mensagem(dados, incluir_link=True):
    texto = f"""{dados['esporte']}
🏆 {dados['linha_odd']}
⚔ Confronto: {dados['confronto']}
🔢 Placar: {dados['placar']}
🕒 Tempo: {dados['tempo']}"""

    if not incluir_link and dados['status']:
        texto += f"\n\n{dados['status']}"
    elif incluir_link and dados['link']:
        texto += f"\n\n🔗 {dados['link']}"
    return texto

# === DESATIVAR WEBHOOK (se configurado) ===
async def desativar_webhook(bot):
    # Tenta remover o webhook caso tenha sido configurado
    try:
        await bot.delete_webhook()
        print("Webhook desativado.")
    except Exception as e:
        print(f"Erro ao desativar webhook: {e}")

# === MENSAGENS NOVAS NO CANAL A ===
async def nova_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.channel_post and update.channel_post.text:
        msg = update.channel_post
        dados = extrair_dados(msg.text)

        if dados['linha_odd'] and dados['confronto']:
            texto = formatar_mensagem(dados, incluir_link=True)
            enviada = await context.bot.send_message(chat_id=DESTINO_CHAT_ID, text=texto)

            cursor.execute('INSERT INTO mensagens (origem_msg_id, destino_msg_id) VALUES (?, ?)',
                           (msg.message_id, enviada.message_id))
            conn.commit()

# === EDIÇÕES NO CANAL A ===
async def mensagem_editada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.edited_channel_post and update.edited_channel_post.text:
        msg = update.edited_channel_post
        dados = extrair_dados(msg.text)

        if dados['status']:
            cursor.execute('SELECT destino_msg_id FROM mensagens WHERE origem_msg_id = ?', (msg.message_id,))
            resultado = cursor.fetchone()

            if resultado:
                destino_msg_id = resultado[0]
                texto_editado = formatar_mensagem(dados, incluir_link=False)
                await context.bot.edit_message_text(chat_id=DESTINO_CHAT_ID, message_id=destino_msg_id, text=texto_editado)

# === RODAR BOT ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Desativa o webhook antes de rodar o polling
    await desativar_webhook(app.bot)

    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, nova_mensagem))
    app.add_handler(MessageHandler(filters.UpdateType.EDITED_CHANNEL_POST, mensagem_editada))

    print("✅ Bot está rodando... esperando mensagens do canal origem.")
    await app.run_polling()  # Aqui o framework gerencia o loop de eventos

# === EXECUTA O BOT DIRETAMENTE COM O LOOP DE EVENTOS CORRETO ===
if __name__ == '__main__':
    # Apenas rodamos o polling diretamente, sem a necessidade de asyncio.run()
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())  # Não criamos um novo loop, apenas usa o atual.
