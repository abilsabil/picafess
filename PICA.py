import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN") or "GANTI_TOKEN_MU"
DATA_FILE = "confession_data.json"

# ID Channel Log (Hardcoded karena ini untuk Owner Bot)
DEV_LOG_CHANNEL_ID = 1054292813996638258 

# ID Channel Utama (Ambil dari Variables Railway agar tidak perlu set ulang)
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
        # Jika server baru, gunakan ID dari ENV (jika ada) atau None
        server_data[sid] = {
            "count": 0, 
            "confess_channel_id": int(ENV_CONFESS_ID) if ENV_CONFESS_ID else None, 
            "riddle_channel_id": int(ENV_RIDDLE_ID) if ENV_RIDDLE_ID else None
        }
        save_data(server_data)
    return server_data[sid]

# ================= RIDDLE SYSTEM =================
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
    def __init__(self, creator_id: int = None):
        super().__init__(timeout=None)
        self.creator_id = creator_id

    @discord.ui.button(label="Jawab", style=discord.ButtonStyle.success, custom_id="riddle_ans")
    async def ans_btn(self, itx, btn):
        await itx.response.send_modal(RiddleAnswerModal(itx.message))

    @discord.ui.button(label="Umumkan Pemenang", style=discord.ButtonStyle.danger, custom_id="riddle_win")
    async def win_btn(self, itx, btn):
        if itx.user.id != self.creator_id and not itx.user.guild_permissions.administrator:
            return await itx.response.send_message("Hanya pembuat/Admin yang bisa menutup ini.", ephemeral=True)
        
        modal = discord.ui.Modal(title="Tentukan Pemenang")
        win_user = discord.ui.TextInput(label="Nama Pemenang", placeholder="@User")
        corr_ans = discord.ui.TextInput(label="Jawaban Benar", style=discord.TextStyle.paragraph)
        
        async def modal_submit(itx_sub: discord.Interaction):
            embed = itx_sub.message.embeds[0]
            embed.add_field(name="🎊 PEMENANG", value=f"Selamat kepada {win_user.value}!", inline=False)
            embed.add_field(name="💡 JAWABAN", value=f"**{corr_ans.value}**", inline=False)
            embed.color = discord.Color.gold()
            await itx_sub.response.edit_message(embed=embed, view=None)
            if itx_sub.message.thread:
                await itx_sub.message.thread.send(f"🔒 Riddle Ditutup! Pemenang: {win_user.value}")
        
        modal.on_submit = modal_submit
        modal.add_item(win_user); modal.add_item(corr_ans)
        await itx.response.send_modal(modal)

# ================= CONFESSION SYSTEM =================
class SendConfessModal(discord.ui.Modal, title='Kirim Confess'):
    content = discord.ui.TextInput(label='Isi Confess', style=discord.TextStyle.paragraph, required=True, max_length=2000)
    async def on_submit(self, interaction: discord.Interaction):
        config = get_server_config(interaction.guild_id)
        chan = bot.get_channel(config.get("confess_channel_id"))
        if not chan: return await interaction.response.send_message("❌ Channel belum diatur!", ephemeral=True)
        
        config["count"] += 1
        embed = discord.Embed(title=f"💌 PICAFESS #{config['count']}", description=self.content.value, color=0xff69b4)
        await chan.send(embed=embed)
        save_data(server_data)
        
        # Log Pengirim (Selalu masuk ke channel dev owner)
        dev_log = bot.get_channel(DEV_LOG_CHANNEL_ID)
        if dev_log: await dev_log.send(f"🚀 **Confess** | {interaction.guild.name} | {interaction.user}: {self.content.value}")
        await interaction.response.send_message("✅ Terkirim secara anonim!", ephemeral=True)

# ================= BOT CORE =================
class PicaBot(commands.Bot):
    def __init__(self): super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        self.add_view(RiddleView(0))
        await self.tree.sync()

bot = PicaBot(); tree = bot.tree

@bot.event
async def on_message(message):
    if message.author.bot: return

    # AUTO-EMBED RIDDLE
    if isinstance(message.channel, discord.Thread) and message.channel.name == "Diskusi & Jawaban Riddle":
        content, user = message.content, message.author
        try: await message.delete()
        except: pass
        emb = discord.Embed(description=content, color=discord.Color.blue())
        emb.set_author(name=f"Jawaban dari {user.display_name}", icon_url=user.display_avatar.url)
        await message.channel.send(embed=emb)

    # AUTO-EMBED CONFESS (ANONIM)
    elif isinstance(message.channel, discord.Thread) and message.channel.name == "Komentar":
        content = message.content
        try: await message.delete()
        except: pass
        emb = discord.Embed(description=content, color=discord.Color.light_gray())
        emb.set_author(name="Komentar Anonim", icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
        await message.channel.send(embed=emb)

    await bot.process_commands(message)

@tree.command(name="set-confess-channel")
async def sc(itx, channel: discord.TextChannel):
    if not itx.user.guild_permissions.administrator: return
    get_server_config(itx.guild_id)["confess_channel_id"] = channel.id
    save_data(server_data)
    await itx.response.send_message(f"✅ Channel Confess: {channel.mention}", ephemeral=True)

@tree.command(name="set-riddle-channel")
async def sr(itx, channel: discord.TextChannel):
    if not itx.user.guild_permissions.administrator: return
    get_server_config(itx.guild_id)["riddle_channel_id"] = channel.id
    save_data(server_data)
    await itx.response.send_message(f"✅ Channel Riddle: {channel.mention}", ephemeral=True)

@tree.command(name="riddle-setup")
async def rs(itx, pertanyaan: str):
    config = get_server_config(itx.guild_id)
    chan = bot.get_channel(config.get("riddle_channel_id"))
    if not chan: return await itx.response.send_message("❌ Set channel dulu!", ephemeral=True)
    embed = discord.Embed(title="🧩 PICA RIDDLE", description=f"**Pertanyaan:**\n{pertanyaan}", color=0x2ecc71)
    embed.set_author(name=f"Oleh: {itx.user.display_name}", icon_url=itx.user.display_avatar.url)
    await chan.send(embed=embed, view=RiddleView(itx.user.id))
    await itx.response.send_message("✅ Riddle dikirim!", ephemeral=True)

@tree.command(name="picafess")
async def pf(itx):
    await itx.response.send_modal(SendConfessModal())

@bot.event
async def on_ready(): print(f"Pica Online sebagai {bot.user}")

bot.run(TOKEN)
