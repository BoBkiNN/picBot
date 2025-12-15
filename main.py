import os
import disnake
from disnake.ext import commands
from serpapi import Client
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# Initialize Disnake bot
bot = commands.InteractionBot()

# -------- Dataclass for User Session --------


@dataclass
class ImageSession:
    query: str
    urls: list[str]
    idx: int
    view: disnake.ui.View


# Session store for browsing state
user_sessions: dict[int, ImageSession] = {}

# -------- SerpApi Image Search --------


async def serpapi_search_images(query: str, num: int = 10) -> list[str]:
    client = Client(api_key=SERPAPI_KEY)
    results = client.search({
        "engine": "google_images_light",
        "q": query,
        "num": num
    })
    images = [img.get("original") or img.get("thumbnail")
              for img in results.get("images_results", [])]
    return [img for img in images if img]

# -------- Embed Builder --------


def build_embed(url: str, query: str, idx: int, total: int) -> disnake.Embed:
    emb = disnake.Embed(title=f"Image {idx+1}/{total} for: {query}")
    emb.set_image(url=url)
    return emb

# -------- /pic Command --------


@bot.slash_command(name="pic", description="Search for images by query", install_types=disnake.ApplicationInstallTypes(user=True))
async def pic(inter: disnake.CommandInteraction, query: str):
    await inter.response.defer(ephemeral=True)

    urls = await serpapi_search_images(query, num=10)
    if not urls:
        return await inter.followup.send("No images found.", ephemeral=True)

    # Make view with buttons
    view = disnake.ui.View()
    view.add_item(disnake.ui.Button(
        label="Prev", style=disnake.ButtonStyle.primary, custom_id="prev"))
    view.add_item(disnake.ui.Button(
        label="Next", style=disnake.ButtonStyle.primary, custom_id="next"))
    view.add_item(disnake.ui.Button(label="Confirm",
                  style=disnake.ButtonStyle.success, custom_id="confirm"))

    # Save session using dataclass
    user_sessions[inter.user.id] = ImageSession(
        query=query, urls=urls, idx=0, view=view)

    embed = build_embed(urls[0], query, 0, len(urls))
    await inter.followup.send(embed=embed, view=view, ephemeral=True)
    print(f"User {inter.user.name!r} ({inter.user.id}) requested image {query!r}")

# -------- Button Interaction --------


@bot.listen("on_button_click")
async def handle_buttons(inter: disnake.MessageInteraction):
    user_id = inter.user.id
    session = user_sessions.get(user_id)
    if not session:
        return await inter.response.send_message("Session expired.", ephemeral=True)

    cid = inter.component.custom_id

    if cid == "prev":
        session.idx = (session.idx - 1) % len(session.urls)
    elif cid == "next":
        session.idx = (session.idx + 1) % len(session.urls)
    elif cid == "confirm":
        embed = disnake.Embed(title=f"Image from {inter.user.display_name}")
        url = session.urls[session.idx]
        embed.set_image(url=url)
        await inter.response.send_message(embed=embed, ephemeral=False)
        print(
            f"✅ User {inter.user.name!r} ({inter.user.id}) confirmed image {session.query!r}: {url}")
        return

    # Edit ephemeral message with new image
    new_embed = build_embed(
        session.urls[session.idx], session.query, session.idx, len(session.urls))
    await inter.response.edit_message(embed=new_embed, view=session.view)


@bot.event
async def on_ready():
    print(
        f"✅ Bot connected: APP ID: {bot.application_id}; Name: {bot.user.name}")

# -------- Run Bot --------
bot.run(BOT_TOKEN)
