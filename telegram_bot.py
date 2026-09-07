import asyncio
import time
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig
from google.antigravity.policy import allow_all

class AgentManager:
    def __init__(self):
        self.queue = asyncio.Queue()
        
    async def start(self):
        asyncio.create_task(self.run_agent())
        
    async def run_agent(self):
        config = LocalAgentConfig(
            api_key=os.environ["ANTIGRAVITY_API_KEY"],
            system_instructions=(
                "Jsi expert programátor v Antigravity IDE. Tvé odpovědi jsou posílány uživateli přes Telegram bota na mobil. "
                "Upravuj a vytvářej soubory v projektu uživatele podle jeho pokynů. Odpovídej stručně, jasně a v češtině."
            ),
            capabilities=CapabilitiesConfig(),
            policies=[allow_all()]
        )
        while True:
            try:
                async with Agent(config) as agent:
                    print("Antigravity Agent spuštěn.")
                    while True:
                        msg, status_queue = await self.queue.get()
                        
                        try:
                            print(f"Předávám zprávu agentovi: {msg}")
                            response = await agent.chat(msg)
                            
                            # Spustíme paralelně naslouchání myšlenek a nástrojů
                            async def consume_thoughts():
                                async for thought in response.thoughts:
                                    await status_queue.put(f"💭 {thought}")
                                    
                            async def consume_tools():
                                async for call in response.tool_calls:
                                    await status_queue.put(f"🛠️ Používám nástroj: {call.name}")
                            
                            asyncio.create_task(consume_thoughts())
                            asyncio.create_task(consume_tools())
                            
                            # Hlavní loop pro čtení odpovědi
                            full_reply = ""
                            async for token in response:
                                full_reply += token
                                
                            if not full_reply.strip():
                                full_reply = "Úkol byl dokončen (agent neposlal žádný textový komentář)."
                                
                            await status_queue.put(f"FINAL_REPLY:{full_reply}")
                        except Exception as e:
                            print(f"Chyba agenta: {e}")
                            await status_queue.put(f"FINAL_REPLY:Chyba agenta (pravděpodobně limit API). Zkuste to za 30 vteřin znovu: {e}")
                            break # Restart agenta po chybě
            except Exception as e:
                print(f"Chyba při startu agenta: {e}")
                await asyncio.sleep(2)

agent_manager = AgentManager()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"Přijata zpráva z mobilu: {user_text}")
    
    wait_msg = await update.message.reply_text("⏳ Agent pracuje na tvém požadavku...")
    
    status_queue = asyncio.Queue()
    await agent_manager.queue.put((user_text, status_queue))
    
    last_text = "⏳ Agent pracuje..."
    last_edit_time = time.time()
    
    while True:
        status = await status_queue.get()
        
        if status.startswith("FINAL_REPLY:"):
            reply = status[len("FINAL_REPLY:"):]
            try:
                if len(reply) > 4000:
                    reply = reply[:4000] + "\n... (text byl zkrácen)"
                await wait_msg.edit_text(reply)
            except Exception as e:
                await update.message.reply_text(f"Hotovo, ale nastala chyba při odpovídání: {e}\n\n{reply}")
            break
        else:
            # Průběžná aktualizace
            new_text = f"⏳ Agent pracuje...\n\nAktuální činnost:\n{status}"
            
            # Abychom nepřehltili Telegram (limit 1 úprava za 1-2 vteřiny)
            if new_text != last_text and (time.time() - last_edit_time > 1.5):
                try:
                    await wait_msg.edit_text(new_text)
                    last_text = new_text
                    last_edit_time = time.time()
                except Exception:
                    pass

async def post_init(application):
    await agent_manager.start()

if __name__ == '__main__':
    TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
    
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Spouštím Telegram bota (VERZE S ŽIVÝM SLEDOVÁNÍM)...")
    app.run_polling()
