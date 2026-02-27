import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import hashlib

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

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

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

# ================= CAROUSEL VIEW =================
class PicafessView(discord.ui.View):
    def __init__(self, images, current_index=0):
        super().__init__(timeout=None)
        self.images = images
        self.index = current_index

    def update_buttons(self):
        self.back_button.disabled = (self.index == 0)
        self.next_button.disabled = (self.index == len(self.images) - 1)
        self.page_label.label = f"{self.index + 1}/{len(self.images)}"

    @discord.ui.button(label="◀", style=discord.ButtonStyle.gray, custom_id="prev_img")
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index -= 1
        self.update_buttons()
        embed = interaction.message.embeds[0]
        embed.set_image(url=self.images[self.index])
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.gray, disabled=True, custom_id="page_num")
    async def page_label(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="▶", style=discord.ButtonStyle.gray, custom_id="next_img")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index += 1
        self.update_buttons()
        embed = interaction.message.embeds[0]
        embed.set_image(url=self.images[self.index])
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, custom_id="persistent_delete_confess")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin_or_privileged(interaction):
            await interaction.response.send_message("Hanya Admin/Staff yang bisa menghapus.", ephemeral=True)
            return
        try: await interaction.message.delete()
        except: pass

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
            view = discord.ui.View(timeout=None)
            delete_btn = discord.ui.Button(label="Delete", style=discord.ButtonStyle.danger, custom_id="p_del")
            async def d_cb(it):
                if is_admin_or_privileged(it): await it.message.delete()
                else: await it.response.send_message("No Perms.", ephemeral=True)
            delete_btn.callback = d_cb
            view.add_item(delete_btn)
    else:
        view = discord.ui.View(timeout=None)
        delete_btn = discord.ui.Button(label="Delete", style=discord.ButtonStyle.danger, custom_id="p_del")
        async def d_cb(it):
            if is_admin_or_privileged(it): await it.message.delete()
            else: await it.response.send_message("No Perms.", ephemeral=True)
        delete_btn.callback = d_cb
        view.add_item(delete_btn)

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
    await tree.sync()
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="/picafess"))
    print(f"Bot Online: {bot.user}")

bot.run(TOKEN)