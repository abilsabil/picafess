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

# --- Tambahan Fungsi Panduan (Tanpa ubah struktur) ---
async def send_welcome_info(guild, config):
    """Mengirim pesan panduan ke channel yang terdaftar jika bot punya izin"""
    # Welcome Confess
    conf_id = config.get("confess_channel_id")
    if conf_id:
        chan = guild.get_channel(conf_id)
        if chan and chan.permissions_for(guild.me).send_messages:
            emb = discord.Embed(title="🌸 Welcome to Picafess!", 
                               description="Gunakan `/picafess` untuk kirim pesan anonim.\nKomentar di thread juga bersifat anonim.", 
                               color=0xff69b4)
            await chan.send(embed=emb)

    # Welcome Riddle
    rid_id = config.get("riddle_channel_id")
    if rid_id:
        chan = guild.get_channel(rid_id)
        if chan and chan.permissions_for(guild.me).send_messages:
            emb = discord.Embed(title="🧩 Welcome to Pica Riddle!", 
                               description="Gunakan `/riddle-setup` untuk buat teka-teki.\nKlik 'Jawab' untuk berpartisipasi!", 
                               color=0x2ecc71)
            await chan.send(embed=emb)

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
        msg = await chan.send(embed=embed)
        await msg.create_thread(name="Komentar", auto_archive_duration=1440) # Otomatis buat thread komentar
        save_data(server_data)
        
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

# --- Event untuk Auto Welcome saat Bot dikasih Role ---
@bot.event
async def on_member_update(before, after):
    if after.id == bot.user.id and len(before.roles) < len(after.roles):
        config = get_server_config(after.guild.id)
        await asyncio.sleep(2) # Tunggu sync permission
        await send_welcome_info(after.guild, config)

@bot.event
async def on_message(message):
    if message.author.bot: return

    if isinstance(message.channel, discord.Thread) and message.channel.name == "Diskusi & Jawaban Riddle":
        content, user = message.content, message.author
        try: await message.delete()
        except: pass
        emb = discord.Embed(description=content, color=discord.Color.blue())
        emb.set_author(name=f"Jawaban dari {user.display_name}", icon_url=user.display_avatar.url)
        await message.channel.send(embed=emb)

    elif isinstance(message.channel, discord.Thread) and message.channel.name == "Komentar":
        content = message.content
        try: await message.delete()
        except: pass
        emb = discord.Embed(description=content, color=discord.Color.light_gray())
        emb.set_author(name="Komentar Anonim", icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
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

@tree.command(name="setup-info", description="Kirim ulang panduan welcome")
async def s_info(itx):
    if not itx.user.guild_permissions.administrator: return
    config = get_server_config(itx.guild_id)
    await send_welcome_info(itx.guild, config)
    await itx.response.send_message("✅ Mencoba mengirim ulang panduan...", ephemeral=True)

@tree.command(name="reset-data", description="Reset counter dan setting (Admin Only)")
async def reset_data(itx):
    if not itx.user.guild_permissions.administrator: return
    server_data[str(itx.guild_id)] = {"count": 0, "confess_channel_id": None, "riddle_channel_id": None}
    save_data(server_data)
    await itx.response.send_message("✅ Data server ini telah direset!", ephemeral=True)

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
