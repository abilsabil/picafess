import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN") or "InsertToken"
DATA_FILE = "confession_data.json"
DEV_LOG_CHANNEL_ID = 1054292813996638258 
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
    except Exception: return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
    except Exception as e: print(f"Gagal simpan data: {e}")

server_data = load_data()

def get_server_config(guild_id):
    sid = str(guild_id)
    if sid not in server_data:
        server_data[sid] = {"count": 0, "confessions": {}, "confess_channel_id": None, "riddle_channel_id": None, "admin_role_id": None}
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

# ================= RIDDLE SYSTEM (BARU) =================
class RiddleAnswerModal(discord.ui.Modal, title='Kirim Jawaban Riddle'):
    answer_input = discord.ui.TextInput(
        label='Jawabanmu',
        style=discord.TextStyle.paragraph,
        placeholder='Tulis jawabanmu di sini...',
        required=True,
        max_length=500
    )

    def __init__(self, original_message: discord.Message):
        super().__init__()
        self.original_message = original_message

    async def on_submit(self, interaction: discord.Interaction):
        # Membuat atau mendapatkan thread komentar
        thread = self.original_message.thread
        if not thread:
            thread = await self.original_message.create_thread(name="Diskusi & Jawaban Riddle", auto_archive_duration=1440)

        embed = discord.Embed(description=self.answer_input.value, color=discord.Color.blue())
        embed.set_author(name=f"Jawaban dari {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        
        await thread.send(content=f"{interaction.user.mention}", embed=embed)
        await interaction.response.send_message("✅ Jawabanmu telah dikirim ke thread komentar!", ephemeral=True)

class RiddleView(discord.ui.View):
    def __init__(self, creator_id: int = None):
        super().__init__(timeout=None)
        self.creator_id = creator_id

    @discord.ui.button(label="Jawab", style=discord.ButtonStyle.success, custom_id="riddle_answer_btn")
    async def answer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RiddleAnswerModal(interaction.message))

    @discord.ui.button(label="Umumkan Pemenang", style=discord.ButtonStyle.danger, custom_id="riddle_announce_btn")
    async def announce_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator_id and not is_admin_or_privileged(interaction):
            return await interaction.response.send_message("Hanya pembuat/Admin yang bisa menutup ini.", ephemeral=True)
        
        modal = discord.ui.Modal(title="Set Pemenang & Jawaban")
        winner_input = discord.ui.TextInput(label="Nama Pemenang", placeholder="@User", required=True)
        answer_input = discord.ui.TextInput(label="Jawaban Benar (Penjelasan)", placeholder="Jelaskan jawaban yang benar...", required=True)
        
        async def modal_submit(itx: discord.Interaction):
            embed = itx.message.embeds[0]
            embed.add_field(name="🎊 PEMENANG", value=f"Selamat kepada {winner_input.value}!", inline=False)
            embed.add_field(name="💡 JAWABAN BENAR", value=f"**{answer_input.value}**", inline=False)
            embed.color = discord.Color.gold()
            await itx.response.edit_message(embed=embed, view=None)
            if itx.message.thread:
                await itx.message.thread.send(f"🔒 **Riddle ditutup!** Pemenangnya adalah {winner_input.value}.")

        modal.on_submit = modal_submit
        modal.add_item(winner_input)
        modal.add_item(answer_input)
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
        await interaction.response.send_message("✅ Terkirim!", ephemeral=True)

class SendConfessModal(discord.ui.Modal, title='Kirim Confess'):
    confess_content = discord.ui.TextInput(label='Isi Confess', style=discord.TextStyle.paragraph, required=True, max_length=2000)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        config = get_server_config(interaction.guild_id)
        channel = bot.get_channel(config.get("confess_channel_id"))
        if not channel: return await interaction.followup.send("❌ Channel belum diatur!", ephemeral=True)
        config["count"] += 1
        embed = discord.Embed(title=f"💌 PICAFESS #{config['count']}", description=self.confess_content.value, color=DEFAULT_COLOR)
        await channel.send(embed=embed, view=PersistentConfessionView())
        save_data(server_data)
        dev_log = bot.get_channel(DEV_LOG_CHANNEL_ID)
        if dev_log: await dev_log.send(f"🚀 **Confess** | {interaction.user}: {self.confess_content.value}")
        await interaction.followup.send("✅ Terkirim!", ephemeral=True)

class PersistentConfessionView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Confess", style=discord.ButtonStyle.primary, custom_id="pc_btn")
    async def c_btn(self, itx, btn): await itx.response.send_modal(SendConfessModal())
    @discord.ui.button(label="Komentar", style=discord.ButtonStyle.secondary, custom_id="pr_btn")
    async def r_btn(self, itx, btn): await itx.response.send_modal(ReplyModal(itx.message))
    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, custom_id="pd_btn")
    async def d_btn(self, itx, btn):
        if is_admin_or_privileged(itx): await itx.message.delete()
        else: await itx.response.send_message("Hanya Admin yang bisa.", ephemeral=True)

# ================= BOT CORE =================
class PicaBot(commands.Bot):
    def __init__(self): super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        self.add_view(PersistentConfessionView())
        self.add_view(RiddleView())
        await self.tree.sync()

bot = PicaBot(); tree = bot.tree

@tree.command(name="set-confess-channel")
async def sc(itx, channel: discord.TextChannel):
    if not is_admin_or_privileged(itx): return
    get_server_config(itx.guild_id)["confess_channel_id"] = channel.id
    save_data(server_data)
    await itx.response.send_message(f"✅ Channel Confess: {channel.mention}", ephemeral=True)

@tree.command(name="set-riddle-channel")
async def sr(itx, channel: discord.TextChannel):
    if not is_admin_or_privileged(itx): return
    get_server_config(itx.guild_id)["riddle_channel_id"] = channel.id
    save_data(server_data)
    await itx.response.send_message(f"✅ Channel Riddle: {channel.mention}", ephemeral=True)

@tree.command(name="reset-all-channels")
async def reset_all(itx):
    if not is_admin_or_privileged(itx): return
    config = get_server_config(itx.guild_id)
    config["confess_channel_id"] = None
    config["riddle_channel_id"] = None
    save_data(server_data)
    await itx.response.send_message("🗑️ Semua channel direset.", ephemeral=True)

@tree.command(name="riddle-setup")
async def rs(itx, pertanyaan: str):
    config = get_server_config(itx.guild_id)
    chan = bot.get_channel(config.get("riddle_channel_id"))
    if not chan: return await itx.response.send_message("❌ Channel Riddle belum diatur!", ephemeral=True)
    
    await itx.response.send_message("Membuat riddle...", ephemeral=True)
    await itx.delete_original_response()
    
    embed = discord.Embed(title="🧩 PICA RIDDLE", description=f"**Pertanyaan:**\n{pertanyaan}", color=0x2ecc71)
    embed.set_author(name=f"Oleh: {itx.user.display_name}", icon_url=itx.user.display_avatar.url)
    embed.set_footer(text="Klik 'Jawab' untuk mengirim jawabanmu ke thread!")
    
    await chan.send(embed=embed, view=RiddleView(itx.user.id))

@tree.command(name="picafess")
async def pf(itx, message: str = None):
    await itx.response.send_modal(SendConfessModal())

@bot.event
async def on_ready(): print(f"Bot Online: {bot.user}")

bot.run(TOKEN)
