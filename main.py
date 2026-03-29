import os
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import time

# --- KURULUM ---
intents = discord.Intents.default()
intents.message_content = True

class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.start_time = 0
        self.current_song = None

    async def setup_hook(self):
        await self.tree.sync()
        print(f"--- {self.user.name} TÜM ÖZELLİKLERLE AKTİF ---")

bot = MusicBot()

# --- YARDIMCI: İLERLEME ÇUBUĞU ---
def create_progress_bar(current, total):
    size = 15
    if total == 0: return "🔴 Canlı Yayın"
    percentage = min(current / total, 1.0)
    progress = int(size * percentage)
    bar = "▬" * progress + "🔘" + "▬" * (size - progress)
    
    def format_time(seconds):
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"
    
    return f"{format_time(current)} [{bar}] {format_time(total)}"

# --- YOUTUBE & COOKIE AYARLARI ---
base_path = os.path.dirname(os.path.abspath(__file__))
cookie_path = os.path.join(base_path, 'cookies.txt')

YDL_OPTS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'nocheckcertificate': True,
    'source_address': '0.0.0.0',
    'cookiefile': cookie_path, # Çerez dosyasını burada tanımladık
}

FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

# --- AUTOCOMPLETE (Arama Önerileri) ---
async def song_autocomplete(interaction: discord.Interaction, current: str):
    if not current or len(current) < 3: return []
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'default_search': 'ytsearch'}) as ydl:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, lambda: ydl.extract_info(f"ytsearch5:{current}", download=False)['entries'])
            return [app_commands.Choice(name=f"{s['title'][:80]}", value=s['url']) for s in results]
    except: return []

# --- BUTON PANELİ ---
class MusicControl(discord.ui.View):
    def __init__(self, bot, total_duration):
        super().__init__(timeout=None)
        self.bot = bot
        self.total = total_duration

    @discord.ui.button(label="Güncelle", style=discord.ButtonStyle.green, emoji="🔄")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc or not self.bot.current_song:
            return await interaction.response.send_message("Şu an bir şey çalmıyor.", ephemeral=True)
        
        elapsed = time.time() - self.bot.start_time
        bar = create_progress_bar(elapsed, self.total)
        
        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="İlerleme", value=f"```\n{bar}\n```", inline=False)
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="Durdur/Devam", style=discord.ButtonStyle.blurple, emoji="⏯️")
    async def pp(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc:
            if vc.is_playing(): vc.pause()
            elif vc.is_paused(): vc.resume()
        await interaction.response.defer()

    @discord.ui.button(label="Ayrıl", style=discord.ButtonStyle.red, emoji="⏹️")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
        await interaction.response.defer()

# --- OYNAT KOMUTU ---
@bot.tree.command(name="oynat", description="Müzik çalar (YouTube + Çerez Desteği)")
@app_commands.autocomplete(sorgu=song_autocomplete)
async def oynat(interaction: discord.Interaction, sorgu: str):
    await interaction.response.defer(thinking=True)
    
    if not interaction.user.voice:
        return await interaction.followup.send("❌ Önce bir ses kanalına katılmalısın!", ephemeral=True)

    try:
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect(reconnect=True, timeout=60, self_deaf=True)
    except Exception as e:
        return await interaction.followup.send(f"❌ Bağlantı hatası: {e}", ephemeral=True)

    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = await asyncio.get_event_loop().run_in_executor(None, lambda: ydl.extract_info(sorgu, download=False))
            if 'entries' in info: info = info['entries'][0]

            url2 = info['url']
            source = discord.FFmpegPCMAudio(url2, **FFMPEG_OPTS)
            
            total_sec = info.get("duration", 0)
            bot.start_time = time.time()
            bot.current_song = info["title"]
            bar = create_progress_bar(0, total_sec)

            embed = discord.Embed(title=f"🎶 Çalıyor: {info['title']}", color=0xFF0000, url=info.get('webpage_url'))
            embed.add_field(name="İlerleme", value=f"```\n{bar}\n```", inline=False)
            if info.get("thumbnail"): embed.set_image(url=info["thumbnail"])

            if vc.is_playing(): vc.stop()
            
            vc.play(source)
            await interaction.followup.send(embed=embed, view=MusicControl(bot, total_sec))
            
    except Exception as e:
        print(f"Hata: {e}")
        error_msg = str(e)
        if "Sign in to confirm" in error_msg:
            await interaction.followup.send("⚠️ YouTube Çerez hatası! Lütfen cookies.txt dosyasını yenileyin.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ Hata oluştu: `{error_msg[:100]}`", ephemeral=True)

# --- ÇALIŞTIR ---
if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("HATA: DISCORD_TOKEN bulunamadı!")
