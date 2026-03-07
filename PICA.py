import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN") or "GANTI_TOKEN_MU"
DATA_FILE = "confession_data.json"
DEV_LOG_CHANNEL_ID = 1054292813996638258 
ENV_CONFESS_ID = os.getenv("CONFESS_CHANNEL_ID")
ENV_RIDDLE_ID = os.getenv("RIDDLE_CHANNEL_ID")
# ==========================================

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True 
intents.members = True 

# ================= DATA SYSTEM =================
def load_data():
    if not os.path.exists(DATA_FILE) or os.stat(DATA_FILE).st_size == 0:
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except: return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e: print(f"Error saving: {e}")

server_data = load_data()

def get_server_config(guild_id):
    sid = str(guild_id)
    if sid not in server_data:
        server_data[sid] = {
            "count": 0, 
            "confess_channel_id": int(ENV_CONFESS_ID) if ENV_CONFESS_ID else None, 
            "riddle_channel_id": int(ENV_RIDDLE_ID) if ENV_RIDDLE_ID else None
        }
        save_data(server_data)
    return server_data[sid]

# ================= UI COMPONENTS =================

class ConfessLaunchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Kirim Confess (Anonim)", style=discord.ButtonStyle.primary, custom_id="persistent_confess_btn")
    async def confess_button(self, itx: discord.Interaction, button: discord.ui.Button):
        await itx.response.send_modal(SendConfessModal())

class SendConfessModal(discord.ui.Modal, title='Unburden Your Mind'):
    content = discord.ui.TextInput(label='Tulis curhatanmu...', style=discord.TextStyle.paragraph, required=True, max_length=2000)
    async def on_submit(self, interaction: discord.Interaction):
        config = get_server_config(interaction.guild_id)
        chan = bot.get_channel(config.get("confess_channel_id"))
        if not chan: return await interaction.response.send_message("❌ Channel belum diatur!", ephemeral=True)
        config["count"] += 1
        embed = discord.Embed(title=f"💌 PICAFESS #{config['count']}", description=self.content.value, color=0xff69b4)
        await chan.send(embed=embed)
        save_data(server_data)
        dev_log = bot.get_channel(DEV_LOG_CHANNEL_ID)
        if dev_log: await dev_log.send(f"🚀 **Confess** | {interaction.guild.name} | {interaction.user}: {self.content.value}")
        await interaction.response.send_message("✅ Terkirim!", ephemeral=True)

# --- Riddle UI ---
class RiddleAnswerModal(discord.ui.Modal, title='Kirim Jawaban Riddle'):
    ans = discord.ui.TextInput(label='Jawabanmu', style=discord.TextStyle.paragraph, required=True)
    def __init__(self, original_msg: discord.Message):
        super().__init__()
        self.original_msg = original_msg
    async def on_submit(self, interaction: discord.Interaction):
        thread = self.original_msg.thread or await self.original_msg.create_thread(name="Diskusi & Jawaban Riddle", auto_archive_duration=1440)
        emb = discord.Embed(description=self.ans.value, color=discord.Color.blue())
        emb.set_author(name=f"Jawaban dari {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await thread.send(embed=emb)
        await interaction.response.send_message("✅ Jawaban terkirim ke thread!", ephemeral=True)

class RiddleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Jawab", style=discord.ButtonStyle.success, custom_id="riddle_ans")
    async def ans_btn(self, itx, btn):
        await itx.response.send_modal(RiddleAnswerModal(itx.message))

async def send_welcome_info(guild, config):
    """MENGIRIM PESAN WELCOME KE KEDUA CHANNEL"""
    # Welcome Confess
    conf_id = config.get("confess_channel_id")
    if conf_id:
        chan = guild.get_channel(conf_id)
        if chan and chan.permissions_for(guild.me).send_messages:
            emb = discord.Embed(title="🌸 Welcome to Unburden!", description="Klik tombol untuk **Confess** atau ketik langsung untuk **Komentar**.", color=0xff69b4)
            await chan.send(embed=emb, view=ConfessLaunchView())

    # Welcome Riddle
    rid_id = config.get("riddle_channel_id")
    if rid_id:
        chan = guild.get_channel(rid_id)
        if chan and chan.permissions_for(guild.me).send_messages:
            emb = discord.Embed(title="🧩 Welcome to Pica Riddle!", description="Gunakan `/riddle-setup` untuk membuat tantangan.\nKlik **Jawab** pada riddle yang aktif untuk ikut serta!", color=0x2ecc71)
            await chan.send(embed=emb)

# ================= BOT CORE =================
class PicaBot(commands.Bot):
    def __init__(self): super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        self.add_view(ConfessLaunchView()) 
        self.add_view(RiddleView())
        await self.tree.sync()

bot = PicaBot(); tree = bot.tree

@bot.event
async def on_message(message):
    if message.author.bot: return
    config = get_server_config(message.guild.id)
    
    # Auto-Embed Komentar di Channel Confess
    if message.channel.id == config.get("confess_channel_id"):
        if not message.content: return
        content = message.content
        try: await message.delete()
        except: pass
        emb = discord.Embed(description=content, color=discord.Color.light_gray())
        emb.set_author(name="Komentar Anonim", icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
        if message.reference: emb.set_footer(text="Membalas pesan ↑")
        await message.channel.send(embed=emb)
        
    # Auto-Embed Jawaban di Thread Riddle
    elif isinstance(message.channel, discord.Thread) and "Riddle" in message.channel.name:
        content = message.content
        user = message.author
        try: await message.delete()
        except: pass
        emb = discord.Embed(description=content, color=discord.Color.blue())
        emb.set_author(name=f"Jawaban dari {user.display_name}", icon_url=user.display_avatar.url)
        await message.channel.send(embed=emb)

    await bot.process_commands(message)

# ================= COMMANDS =================
@tree.command(name="set-confess-channel")
async def sc(itx, channel: discord.TextChannel):
    if not itx.user.guild_permissions.administrator: return
    config = get_server_config(itx.guild_id)
    config["confess_channel_id"] = channel.id
    save_data(server_data)
    await itx.response.send_message(f"✅ Channel Confess: {channel.mention}", ephemeral=True)
    await send_welcome_info(itx.guild, config)

@tree.command(name="set-riddle-channel")
async def sr(itx, channel: discord.TextChannel):
    if not itx.user.guild_permissions.administrator: return
    config = get_server_config(itx.guild_id)
    config["riddle_channel_id"] = channel.id
    save_data(server_data)
    await itx.response.send_message(f"✅ Channel Riddle: {channel.mention}", ephemeral=True)
    await send_welcome_info(itx.guild, config)

@tree.command(name="reset-data")
async def r_data(itx: discord.Interaction):
    await itx.response.defer(ephemeral=True)
    sid = str(itx.guild_id)
    server_data[sid] = {"count": 0, "confess_channel_id": None, "riddle_channel_id": None}
    save_data(server_data)
    await itx.followup.send("✅ Data direset!")

@tree.command(name="setup-info")
async def s_info(itx):
    if not itx.user.guild_permissions.administrator: return
    await send_welcome_info(itx.guild, get_server_config(itx.guild_id))
    await itx.response.send_message("✅ Info dikirim ke semua channel yang terdaftar!", ephemeral=True)

@tree.command(name="riddle-setup")
async def rs(itx, pertanyaan: str):
    config = get_server_config(itx.guild_id)
    chan = bot.get_channel(config.get("riddle_channel_id"))
    if not chan: return await itx.response.send_message("❌ Set channel riddle dulu!", ephemeral=True)
    
    # PERUBAHAN DI SINI: Mengubah string \n menjadi enter sungguhan
    pertanyaan_rapi = pertanyaan.replace("\\n", "\n")
    
    embed = discord.Embed(title="🧩 PICA RIDDLE", description=f"**Pertanyaan:**\n{pertanyaan_rapi}", color=0x2ecc71)
    embed.set_author(name=f"Oleh: {itx.user.display_name}", icon_url=itx.user.display_avatar.url)
    await chan.send(embed=embed, view=RiddleView())
    await itx.response.send_message("✅ Riddle dikirim!", ephemeral=True)

@tree.command(name="picafess")
async def pf(itx): await itx.response.send_modal(SendConfessModal())

@bot.event
async def on_ready(): print(f"Pica Online: {bot.user}")

bot.run(TOKEN)
