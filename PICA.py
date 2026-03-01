import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN") or "InsertToken"
DATA_FILE = "confession_data.json"
DEV_LOG_CHANNEL_ID = 1054292813996638258  # Ganti dengan ID channel log pribadimu
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
        server_data[sid] = {"count": 0, "confessions": {}, "channel_id": None, "admin_role_id": None}
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

# ================= RIDDLE MODALS & VIEWS =================
class RiddleAnswerModal(discord.ui.Modal, title='Jawab Riddle'):
    answer_input = discord.ui.TextInput(
        label='Jawabanmu',
        placeholder='Ketik jawaban di sini...',
        required=True,
        max_length=100
    )

    def __init__(self, correct_answer: str, riddle_text: str):
        super().__init__()
        self.correct_answer = correct_answer.lower().strip()
        self.riddle_text = riddle_text

    async def on_submit(self, interaction: discord.Interaction):
        user_answer = self.answer_input.value.lower().strip()
        
        if user_answer == self.correct_answer:
            dev_log = bot.get_channel(DEV_LOG_CHANNEL_ID)
            if dev_log:
                await dev_log.send(
                    f"🏆 **Pemenang Riddle!**\n"
                    f"User: {interaction.user.mention} ({interaction.user})\n"
                    f"Riddle: {self.riddle_text}\n"
                    f"Jawaban: {self.answer_input.value}"
                )
            await interaction.response.send_message("✅ Jawabanmu benar! Admin telah dinotifikasi. Tunggu pengumumannya ya!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Jawaban salah! Coba lagi ya.", ephemeral=True)

class RiddleView(discord.ui.View):
    def __init__(self, correct_answer: str = "", riddle_text: str = ""):
        super().__init__(timeout=None)
        self.correct_answer = correct_answer
        self.riddle_text = riddle_text

    @discord.ui.button(label="Jawab", style=discord.ButtonStyle.success, custom_id="riddle_answer_btn")
    async def answer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RiddleAnswerModal(self.correct_answer, self.riddle_text))

    @discord.ui.button(label="Umumkan Pemenang", style=discord.ButtonStyle.danger, custom_id="riddle_announce_btn")
    async def announce_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin_or_privileged(interaction):
            await interaction.response.send_message("Hanya Admin yang bisa mengumumkan pemenang.", ephemeral=True)
            return
        
        modal = discord.ui.Modal(title="Set Pemenang")
        winner_input = discord.ui.TextInput(label="Nama/Mention Pemenang", placeholder="Contoh: @User", required=True)
        
        async def modal_submit(itx: discord.Interaction):
            embed = itx.message.embeds[0]
            embed.add_field(name="🎊 PEMENANG", value=f"Selamat kepada {winner_input.value}!", inline=False)
            embed.color = discord.Color.gold()
            await itx.response.edit_message(embed=embed, view=None)

        modal.on_submit = modal_submit
        modal.add_item(winner_input)
        await interaction.response.send_modal(modal)

# ================= CONFESSION MODALS =================
class ReplyModal(discord.ui.Modal, title='Komentar'):
    reply_content = discord.ui.TextInput(
        label='Isi Komentar',
        style=discord.TextStyle.paragraph,
        placeholder='Ketik komentarmu di sini...',
        required=True,
        max_length=1000
    )

    def __init__(self, original_message: discord.Message):
        super().__init__()
        self.original_message = original_message

    async def on_submit(self, interaction: discord.Interaction):
        thread = self.original_message.thread
        if not thread:
            thread = await self.original_message.create_thread(name="Komentar", auto_archive_duration=1440)

        embed = discord.Embed(description=self.reply_content.value, color=discord.Color.light_gray())
        embed.set_author(name="Komentar Anonim", icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
        await thread.send(embed=embed)
        await interaction.response.send_message("✅ Komentarmu berhasil dikirim!", ephemeral=True)

class SendConfessModal(discord.ui.Modal, title='Kirim Confess'):
    confess_content = discord.ui.TextInput(
        label='Isi Confess',
        style=discord.TextStyle.paragraph,
        placeholder='Ketik rahasiamu di sini...',
        required=True,
        max_length=2000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        success, note = await send_confession(interaction.guild, interaction.user, self.confess_content.value, None)
        await interaction.followup.send(note, ephemeral=True)


# ================= VIEWS =================
class PersistentConfessionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Confess", style=discord.ButtonStyle.primary, custom_id="persist_confess_btn")
    async def confess_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SendConfessModal())

    @discord.ui.button(label="Komentar", style=discord.ButtonStyle.secondary, custom_id="persist_reply_btn")
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReplyModal(interaction.message))

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, custom_id="persist_delete_btn")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin_or_privileged(interaction):
            await interaction.response.send_message("Hanya Admin/Staff yang bisa menghapus.", ephemeral=True)
            return
        try: await interaction.message.delete()
        except: pass

class PicafessView(discord.ui.View):
    def __init__(self, images=None, current_index=0):
        super().__init__(timeout=None)
        self.images = images or []
        self.index = current_index

    def update_buttons(self):
        self.back_button.disabled = (self.index == 0)
        self.next_button.disabled = (self.index == len(self.images) - 1)
        self.page_label.label = f"{self.index + 1}/{len(self.images)}"

    @discord.ui.button(label="◀", style=discord.ButtonStyle.gray, custom_id="prev_img", row=0)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.images:
            await interaction.response.send_message("Sistem restart. Gambar tidak bisa digeser lagi.", ephemeral=True)
            return
        self.index -= 1
        self.update_buttons()
        embed = interaction.message.embeds[0]
        embed.set_image(url=self.images[self.index])
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.gray, disabled=True, custom_id="page_num", row=0)
    async def page_label(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="▶", style=discord.ButtonStyle.gray, custom_id="next_img", row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.images:
            await interaction.response.send_message("Sistem restart. Gambar tidak bisa digeser lagi.", ephemeral=True)
            return
        self.index += 1
        self.update_buttons()
        embed = interaction.message.embeds[0]
        embed.set_image(url=self.images[self.index])
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Confess", style=discord.ButtonStyle.primary, custom_id="confess_img_btn", row=1)
    async def confess_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SendConfessModal())

    @discord.ui.button(label="Komentar", style=discord.ButtonStyle.secondary, custom_id="reply_img_btn", row=1)
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReplyModal(interaction.message))

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, custom_id="persistent_delete_confess", row=1)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin_or_privileged(interaction):
            await interaction.response.send_message("Hanya Admin/Staff yang bisa menghapus.", ephemeral=True)
            return
        try: await interaction.message.delete()
        except: pass

# ================= BOT CLASS =================
class PicaBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
    
    async def setup_hook(self):
        self.add_view(PersistentConfessionView())
        self.add_view(PicafessView())
        self.add_view(RiddleView()) # Agar tombol riddle tetap aktif setelah restart
        await self.tree.sync()

bot = PicaBot()
tree = bot.tree

# ================= CORE LOGIC =================
async def send_confession(guild, user, message, attachments=None):
    config = get_server_config(guild.id)
    if not config.get("channel_id"): return False, "Channel belum diatur."

    channel = bot.get_channel(config["channel_id"])
    if not channel: return False, "Bot tidak bisa mengakses channel."

    config["count"] += 1
    conf_num = config["count"]

    embed = discord.Embed(title=f"💌 PICAFESS #{conf_num}", description=message, color=DEFAULT_COLOR)
    
    view = None
    if attachments and len(attachments) > 0:
        img_urls = [a.url for a in attachments]
        embed.set_image(url=img_urls[0])
        if len(img_urls) > 1:
            view = PicafessView(img_urls)
            view.update_buttons()
        else:
            view = PersistentConfessionView()
    else:
        view = PersistentConfessionView()

    msg = await channel.send(embed=embed, view=view)
    config["confessions"][str(msg.id)] = {"number": conf_num, "hearts": 0}
    save_data(server_data)

    dev_log = bot.get_channel(DEV_LOG_CHANNEL_ID)
    if dev_log:
        await dev_log.send(f"🚀 **Dev Log** | Server: {guild.name} | User: {user} | Pesan: {message}")
        
    return True, "Confession terkirim!"

# ================= COMMANDS =================
@tree.command(name="set-channel")
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin_or_privileged(interaction): return
    config = get_server_config(interaction.guild_id)
    config["channel_id"] = channel.id
    save_data(server_data)
    await interaction.response.send_message(f"✅ Channel diatur ke {channel.mention}", ephemeral=True)

@tree.command(name="picafess")
@app_commands.describe(message="Isi confession", image1="Foto 1", image2="Foto 2", image3="Foto 3", image4="Foto 4", image5="Foto 5")
async def picafess(interaction: discord.Interaction, message: str, image1: discord.Attachment=None, image2: discord.Attachment=None, image3: discord.Attachment=None, image4: discord.Attachment=None, image5: discord.Attachment=None):
    if not interaction.guild:
        await interaction.response.send_message("Gunakan di server atau DM bot.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    imgs = [i for i in [image1, image2, image3, image4, image5] if i]
    success, note = await send_confession(interaction.guild, interaction.user, message, imgs)
    await interaction.followup.send(note, ephemeral=True)

@tree.command(name="riddle-setup", description="Admin: Membuat teka-teki baru")
@app_commands.describe(pertanyaan="Isi teka-teki", jawaban="Jawaban benar")
async def riddle_setup(interaction: discord.Interaction, pertanyaan: str, jawaban: str):
    if not is_admin_or_privileged(interaction):
        await interaction.response.send_message("Hanya Admin/Staff yang bisa membuat riddle.", ephemeral=True)
        return

    # Sembunyikan command input
    await interaction.response.send_message("Membuat riddle...", ephemeral=True)
    await interaction.delete_original_response()

    embed = discord.Embed(
        title="🧩 PICA RIDDLE",
        description=f"**Pertanyaan:**\n{pertanyaan}",
        color=0x2ecc71 
    )
    embed.set_footer(text="Klik 'Jawab' untuk mengirim jawaban rahasia ke admin.")
    
    await interaction.channel.send(embed=embed, view=RiddleView(jawaban, pertanyaan))

@bot.event
async def on_message(message):
    if message.author.bot: return
    if isinstance(message.channel, discord.DMChannel):
        shared_guilds = [g for g in bot.guilds if g.get_member(message.author.id)]
        if not shared_guilds: return
        if len(shared_guilds) == 1:
            await send_confession(shared_guilds[0], message.author, message.content, message.attachments)
            await message.author.send(f"✅ Terkirim ke **{shared_guilds[0].name}**")
        else:
            await message.author.send("Gunakan `/picafess` di server tujuan.")
    await bot.process_commands(message)

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="/picafess"))
    print(f"Bot Online: {bot.user}")

bot.run(TOKEN)
