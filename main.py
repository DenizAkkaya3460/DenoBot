import os
import nacl.secret  # Şifreleme motorunu zorla başlatır
import discord
from discord import app_commands
from discord.ext import commands
import nacl.secret
import yt_dlp
import asyncio
import time
import os
from flask import Flask
from threading import Thread

# --- REPLIT 7/24 UYANIK TUTMA (KEEP ALIVE) ---
app = Flask("")


@app.route("/")
def home():
    return "DenoBot 7/24 Aktif!"


def run():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    Thread(target=run).start()


# --- KURULUM ---
intents = discord.Intents.default()
intents.message_content = True


class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.queue = []
        self.current_song = None
        self.start_time = 0

    async def setup_hook(self):
        await self.tree.sync()
        print(f"--- {self.user.name} REPLIT ÜZERİNDE AKTİF ---")


bot = MusicBot()


# --- YARDIMCI FONKSİYON: İLERLEME ÇUBUĞU ---
def create_progress_bar(current, total):
    size = 15
    if total == 0:
        return "🔴 Canlı Yayın"
    percentage = min(current / total, 1.0)
    progress = int(size * percentage)
    bar = "▬" * progress + "🔘" + "▬" * (size - progress)

    def format_time(seconds):
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    return f"{format_time(current)} [{bar}] {format_time(total)}"


# --- AYARLAR ---
FFMPEG_PATH = (
    "/nix/store/60rvdhr04h70r6dyybakaqzbwy15vwdc-replit-runtime-path/bin/ffmpeg"
)
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0', # Render kısıtlamasını aşmaya yardımcı olabilir
}
}
FFMPEG_OPTS = {
    "executable": FFMPEG_PATH,
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


# --- AUTOCOMPLETE ---
async def song_autocomplete(interaction: discord.Interaction, current: str):
    if not current or len(current) < 2:
        return []
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: ydl.extract_info(f"ytsearch5:{current}", download=False)[
                    "entries"
                ],
            )
            return [
                app_commands.Choice(name=f"{s['title'][:80]}", value=s["url"])
                for s in results
            ]
    except:
        return []


# --- BUTON PANELİ ---
class MusicControl(discord.ui.View):
    def __init__(self, bot, total_duration):
        super().__init__(timeout=None)
        self.bot = bot
        self.total = total_duration

    @discord.ui.button(label="Güncelle", style=discord.ButtonStyle.green, emoji="🔄")
    async def refresh(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not interaction.guild.voice_client or not self.bot.current_song:
            return await interaction.response.send_message(
                "Şu an bir şey çalmıyor.", ephemeral=True
            )
        elapsed = time.time() - self.bot.start_time
        bar = create_progress_bar(elapsed, self.total)
        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="İlerleme", value=f"```\n{bar}\n```", inline=False)
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(
        label="Durdur/Devam", style=discord.ButtonStyle.blurple, emoji="⏯️"
    )
    async def pp(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc.is_playing():
            vc.pause()
        elif vc.is_paused():
            vc.resume()
        await interaction.response.defer()

    @discord.ui.button(label="Ayrıl", style=discord.ButtonStyle.red, emoji="⏹️")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
        await interaction.response.defer()


# --- OYNAT KOMUTU ---
@bot.tree.command(name="oynat", description="Müzik ve İlerleme Çubuğu")
@app_commands.autocomplete(sorgu=song_autocomplete)
async def oynat(interaction: discord.Interaction, sorgu: str):
    await interaction.response.defer(thinking=True)
    try:
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.followup.send(
                "❌ Önce bir ses kanalına katılmalısın!", ephemeral=True
            )

        # Mevcut ses bağlantısını temizle
        if (
            interaction.guild.voice_client
            and not interaction.guild.voice_client.is_connected()
        ):
            await interaction.guild.voice_client.disconnect(force=True)

        try:
            vc = (
                interaction.guild.voice_client
                or await interaction.user.voice.channel.connect(
                    reconnect=True, timeout=90, self_deaf=True
                )
            )
        except (asyncio.TimeoutError, Exception) as e:
            print(f"[TIMEOUT/ERROR] Ses bağlantısı başarısız: {type(e).__name__}: {e}")
            try:
                await interaction.followup.send(
                    "❌ Ses kanalına bağlanılamadı. Bu sunucunun ağ bağlantısı Discord ses UDP trafiğini desteklemiyor.",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ydl.extract_info(sorgu, download=False)
            )
            source = discord.FFmpegPCMAudio(info["url"], **FFMPEG_OPTS)
            total_sec = info.get("duration", 0)
            bot.start_time = time.time()
            bot.current_song = info["title"]
            bar = create_progress_bar(0, total_sec)

            embed = discord.Embed(title=f"🎶 Çalıyor: {info['title']}", color=0x2ECC71)
            embed.add_field(name="İlerleme", value=f"```\n{bar}\n```", inline=False)
            if info.get("thumbnail"):
                embed.set_image(url=info["thumbnail"])

            if vc.is_playing():
                vc.stop()
            await asyncio.sleep(1)
            print(f"[PLAYING] URL: {info['url'][:80]}...")
            vc.play(source)
            await interaction.followup.send(
                embed=embed, view=MusicControl(bot, total_sec)
            )
    except Exception as e:
        print(f"[ERROR] oynat hatası: {type(e).__name__}: {e}")
        try:
            await interaction.followup.send(
                f"❌ Bir hata oluştu: `{type(e).__name__}: {e}`", ephemeral=True
            )
        except Exception:
            pass


# --- ÇALIŞTIR ---
if __name__ == "__main__":
    keep_alive()  # Web sunucusunu başlatır
    token = os.environ.get("DISCORD_TOKEN")  # Secrets'tan çeker
    if token:
        bot.run(token)
    else:
        print("MTQ4NzQ1MTU1NjE3MjUyOTY3NA.GAmzc0.Klb0Gx3KrclV-1s9QZfJoX53zCNDgpN-2464Tg")
