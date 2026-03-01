import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN") or "InsertToken"
DATA_FILE = "confession_data.json"
DEFAULT_COLOR = 0xff69b4 
# ==========================================

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True 
intents.reactions = True
intents.members = True 

# ================= DATA SYSTEM =================
def load_data():
    if not os.path.exists(DATA_FILE) or os.stat(DATA_FILE).st_size == 0:
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

server_data = load_data()

def get_server_config(guild_id):
    sid = str(guild_id)
    if sid not in server_data:
        server_data[sid] = {
            "count": 0, 
            "confessions": {}, 
            "confess_channel_id": None, 
            "riddle_channel_id": None, 
            "admin_role_id": None
        }
        save_data(server_data)
    return server_data[sid]

def is_admin_or_privileged(interaction: discord.Interaction):
    if not interaction.guild: return False
    if interaction.user.guild_permissions.administrator: return True
    config = get_server_config(interaction.guild_id)
    admin_role_id = config.get("admin_role_id")
    if admin_role_id:
        role = interaction.guild.get_role(admin_role_id)
        if role in interaction.user.roles: return True
    return False

# ================= RIDDLE SYSTEM =================
class RiddleAnswerModal(discord.ui.Modal, title='Jawab Riddle'):
    answer_input = discord.ui.TextInput(
        label='Jawabanmu',
        placeholder='Ketik jawaban di sini...',
        required=True,
        max_length=100
    )

    def __init__(self, correct_answer: str):
        super().__init__()
        self.correct_answer = correct_answer.lower().strip()

    async def on_submit(self, interaction: discord.Interaction):
        user_answer = self.answer_input.value.lower().strip()
        
        if user_answer == self.correct_answer:
            # Bot langsung memberitahu di channel bahwa user ini benar
            await interaction.channel.send(f"🎉 {interaction.user.mention} menjawab dengan **BENAR**! Tunggu konfirmasi Admin untuk pemenangnya.")
            await interaction.response.send_message("✅ Jawabanmu benar! Kamu sudah disebut di channel.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Jawaban salah! Coba lagi ya.", ephemeral=True)

class RiddleView(discord.ui.View):
    def __init__(self, correct_answer: str = ""):
        super().__init__(timeout=None)
        self.correct_answer = correct_answer

    @discord.ui.button(label="Jawab", style=discord.ButtonStyle.success, custom_id="riddle_answer_btn")
    async def answer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RiddleAnswerModal(self.correct_answer))

    @discord.ui.button(label="Umumkan Pemenang", style=discord.ButtonStyle.danger, custom_id="riddle_announce_btn")
    async def announce_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin_or_privileged(interaction):
            await interaction.response.send_message("Hanya Admin yang bisa mengumumkan pemenang.", ephemeral=True)
            return
        
        modal = discord.ui.Modal(title="Set Pemenang")
        winner_input = discord.ui.TextInput(label="Nama Pemenang", placeholder="Contoh: @User", required=True)
        
        async def modal_submit(itx: discord.Interaction):
            embed = itx.message.embeds[0]
            embed.add_field(name="🎊 PEMENANG RESMI", value=f"Selamat kepada {winner_input.value}!", inline=False)
            embed.color = discord.Color.gold()
            # Hapus tombol setelah diumumkan
            await itx.response.edit_message(embed=embed, view=None)

        modal.on_submit = modal_submit
        modal.add_item(winner_input)
        await interaction.response.send_modal(modal)

# ================= CONFESSION SYSTEM =================
class ReplyModal(discord.ui.Modal, title='Komentar'):
    reply_content = discord.ui.TextInput(label='Isi Komentar', style=discord.TextStyle.paragraph, required=True, max_length=1000)
    def __init__(self, original_message: discord.Message):
        super().__init__()
        self.original_message = original_message
    async def on_submit(self, interaction: discord.Interaction):
        thread = self.original_message.thread or await self.original_message.create_thread(name="Komentar", auto_archive_duration=1440)
        embed = discord.Embed(description=self.reply_content.value, color=discord.Color.light_gray())
        embed.set_author(name="Komentar Anonim", icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
        await thread.send(embed=embed)
        await interaction.response.send_message("✅ Komentarmu terkirim!", ephemeral=True)

class SendConfessModal(discord.ui.Modal, title='Kirim Confess'):
    confess_content = discord.ui.TextInput(label='Isi Confess', style=discord.TextStyle.paragraph, required=True, max_length=2000)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        success, note = await send_confession(interaction.guild, interaction.user, self.confess_content.value, None)
        await interaction.followup.send(note, ephemeral=True)

class PersistentConfessionView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Confess", style=discord.ButtonStyle.primary, custom_id="pc_btn")
    async def c_btn(self, itx, btn): await itx.response.send_modal(SendConfessModal())
    @discord.ui.button(label="Komentar", style=discord.ButtonStyle.secondary, custom_id="pr_btn")
    async def r_btn(self, itx, btn): await itx.response.send_modal(ReplyModal(itx.message))
    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, custom_id="pd_btn")
    async def d_btn(self, itx, btn):
        if is_admin_or_privileged(itx): await itx.message.delete()

# ================= BOT CORE =================
class PicaBot(commands.Bot):
    def __init__(self): super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        self.add_view(PersistentConfessionView()); self.add_view(RiddleView())
        await self.tree.sync()

bot = PicaBot(); tree = bot.tree

async def send_confession(guild, user, message, attachments=None):
    config = get_server_config(guild.id)
    chan_id = config.get("confess_channel_id")
    channel = bot.get_channel(chan_id)
    if not channel: return False, "Channel Confess belum diatur!"
    config["count"] += 1
    embed = discord.Embed(title=f"💌 PICAFESS #{config['count']}", description=message, color=DEFAULT_COLOR)
    msg = await channel.send(embed=embed, view=PersistentConfessionView())
    save_data(server_data)
    return True, "Terkirim!"

# ================= COMMANDS =================
@tree.command(name="set-confess-channel")
async def sc(itx: discord.Interaction, channel: discord.TextChannel):
    if not is_admin_or_privileged(itx): return
    get_server_config(itx.guild_id)["confess_channel_id"] = channel.id
    save_data(server_data)
    await itx.response.send_message(f"✅ Channel Confess: {channel.mention}", ephemeral=True)

@tree.command(name="set-riddle-channel")
async def sr(itx: discord.Interaction, channel: discord.TextChannel):
    if not is_admin_or_privileged(itx): return
    get_server_config(itx.guild_id)["riddle_channel_id"] = channel.id
    save_data(server_data)
    await itx.response.send_message(f"✅ Channel Riddle: {channel.mention}", ephemeral=True)

@tree.command(name="reset-all-channels", description="Admin: Reset semua pengaturan channel")
async def reset_all(itx: discord.Interaction):
    if not is_admin_or_privileged(itx): return
    config = get_server_config(itx.guild_id)
    config["confess_channel_id"] = None
    config["riddle_channel_id"] = None
    save_data(server_data)
    await itx.response.send_message("🗑️ Semua pengaturan channel telah dihapus.", ephemeral=True)

@tree.command(name="riddle-setup")
@app_commands.describe(pertanyaan="Isi teka-teki", jawaban="Jawaban benar")
async def rs(itx: discord.Interaction, pertanyaan: str, jawaban: str):
    if not is_admin_or_privileged(itx): return
    config = get_server_config(itx.guild_id)
    chan = bot.get_channel(config.get("riddle_channel_id"))
    if not chan: 
        await itx.response.send_message("❌ Set channel riddle dulu!", ephemeral=True)
        return
    await itx.response.send_message("Membuat riddle...", ephemeral=True)
    await itx.delete_original_response()
    embed = discord.Embed(title="🧩 PICA RIDDLE", description=f"**Pertanyaan:**\n{pertanyaan}", color=0x2ecc71)
    await chan.send(embed=embed, view=RiddleView(jawaban))

@tree.command(name="picafess")
async def pf(itx: discord.Interaction, message: str):
    await itx.response.defer(ephemeral=True)
    s, n = await send_confession(itx.guild, itx.user, message)
    await itx.followup.send(n, ephemeral=True)

@bot.event
async def on_ready():
    print(f"Bot Online: {bot.user}")

bot.run(TOKEN)
