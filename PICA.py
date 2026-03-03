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

# Tombol khusus untuk diklik di Welcome Message
class ConfessLaunchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Kirim Confess (Anonim)", style=discord.ButtonStyle.primary, custom_id="persistent_confess_btn")
    async def confess_button(self, itx: discord.Interaction, button: discord.ui.Button):
        await itx.response.send_modal(SendConfessModal())

# Modal untuk menulis curhatan
class SendConfessModal(discord.ui.Modal, title='Unburden Your Mind'):
    content = discord.ui.TextInput(
        label='Tulis curhatanmu di sini...', 
        style=discord.TextStyle.paragraph, 
        required=True, 
        max_length=2000,
        placeholder="Apa yang sedang kamu pikirkan?"
    )

    async def on_submit(self, interaction: discord.Interaction):
        config = get_server_config(interaction.guild_id)
        chan = bot.get_channel(config.get("confess_channel_id"))
        if not chan: 
            return await interaction.response.send_message("❌ Channel belum diatur!", ephemeral=True)
        
        config["count"] += 1
        embed = discord.Embed(
            title=f"💌 PICAFESS #{config['count']}", 
            description=self.content.value, 
            color=0xff69b4
        )
        
        await chan.send(embed=embed)
        save_data(server_data)
        
        # Log untuk Developer
        dev_log = bot.get_channel(DEV_LOG_CHANNEL_ID)
        if dev_log: 
            await dev_log.send(f"🚀 **Confess** | {interaction.guild.name} | {interaction.user}: {self.content.value}")
        
        await interaction.response.send_message("✅ Curhatanmu terkirim secara anonim!", ephemeral=True)

# Fungsi kirim pesan sambutan dengan Tombol
async def send_welcome_info(guild, config):
    conf_id = config.get("confess_channel_id")
    if conf_id:
        chan = guild.get_channel(conf_id)
        if chan and chan.permissions_for(guild.me).send_messages:
            emb = discord.Embed(
                title="🌸 Welcome to Unburden!", 
                description="Tempat untuk melepaskan beban pikiran secara anonim.\n\n"
                            "1. Klik tombol di bawah untuk **Confess** (Akan muncul #Nomor).\n"
                            "2. Ketik langsung di channel ini untuk memberi **Komentar** anonim.", 
                color=0xff69b4
            )
            await chan.send(embed=emb, view=ConfessLaunchView())

# ================= RIDDLE SYSTEM (Tetap Ada) =================
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
        await interaction.response.send_message("✅ Terkirim!", ephemeral=True)

class RiddleView(discord.ui.View):
    def __init__(self, creator_id: int = 0):
        super().__init__(timeout=None)
        self.creator_id = creator_id

    @discord.ui.button(label="Jawab", style=discord.ButtonStyle.success, custom_id="riddle_ans")
    async def ans_btn(self, itx, btn):
        await itx.response.send_modal(RiddleAnswerModal(itx.message))

# ================= BOT CORE =================
class PicaBot(commands.Bot):
    def __init__(self): super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        self.add_view(ConfessLaunchView()) # Daftarkan tombol agar tetap aktif setelah restart
        self.add_view(RiddleView())
        await self.tree.sync()

bot = PicaBot(); tree = bot.tree

@bot.event
async def on_message(message):
    if message.author.bot: return

    config = get_server_config(message.guild.id)
    confess_chan_id = config.get("confess_channel_id")

    # LOGIKA KOMENTAR ANONIM
    if message.channel.id == confess_chan_id:
        if not message.content: return
        
        # Simpan isi pesan
        content = message.content
        
        # Hapus pesan asli user
        try: await message.delete()
        except: pass

        # Kirim ulang sebagai Embed Komentar
        emb = discord.Embed(description=content, color=discord.Color.light_gray())
        emb.set_author(name="Komentar Anonim", icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
        
        if message.reference:
            emb.set_footer(text="Membalas pesan ↑")
            
        await message.channel.send(embed=emb)

    # Logika Riddle Thread (Tetap sama)
    elif isinstance(message.channel, discord.Thread) and message.channel.name == "Diskusi & Jawaban Riddle":
        content, user = message.content, message.author
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
    await itx.response.send_message(f"✅ Channel Confess diatur ke {channel.mention}", ephemeral=True)
    await send_welcome_info(itx.guild, config)

@tree.command(name="picafess", description="Kirim curhatan anonim via popup")
async def pf(itx: discord.Interaction):
    await itx.response.send_modal(SendConfessModal())

@tree.command(name="setup-info")
async def s_info(itx):
    if not itx.user.guild_permissions.administrator: return
    config = get_server_config(itx.guild_id)
    await send_welcome_info(itx.guild, config)
    await itx.response.send_message("✅ Pesan selamat datang & tombol dikirim!", ephemeral=True)

@tree.command(name="riddle-setup")
async def rs(itx, pertanyaan: str):
    config = get_server_config(itx.guild_id)
    chan = bot.get_channel(config.get("riddle_channel_id"))
    if not chan: return await itx.response.send_message("❌ Set channel dulu!", ephemeral=True)
    embed = discord.Embed(title="🧩 PICA RIDDLE", description=f"**Pertanyaan:**\n{pertanyaan}", color=0x2ecc71)
    embed.set_author(name=f"Oleh: {itx.user.display_name}", icon_url=itx.user.display_avatar.url)
    await chan.send(embed=embed, view=RiddleView(itx.user.id))
    await itx.response.send_message("✅ Riddle terbit!", ephemeral=True)

@bot.event
async def on_ready(): print(f"Pica Online: {bot.user}")

bot.run(TOKEN)
