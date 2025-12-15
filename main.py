import os
import disnake
from disnake.ext import commands
from serpapi import Client
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# Initialize Disnake bot
bot = commands.InteractionBot(command_sync_flags=commands.CommandSyncFlags.all())

# Session store for browsing state
user_sessions: dict[int, dict] = {}

# -------- SerpApi Image Search --------


async def serpapi_search_images(query: str, num: int = 10) -> list[str]:
    """
    Perform a SerpApi Google Images search and return list of image URLs.
    """
    client = Client(api_key=SERPAPI_KEY)
    results = client.search({
        "engine": "google_images",
        "q": query,
        "num": num
    })
    # Extract usable URLs
    images = [img.get("original") or img.get("thumbnail")
              for img in results.get("images_results", [])]
    return [img for img in images if img]

# -------- Embed Builder --------


def build_embed(url: str, query: str, idx: int, total: int) -> disnake.Embed:
    emb = disnake.Embed(
        title=f"Image {idx+1}/{total} for: {query}"
    )
    emb.set_image(url=url)
    return emb

# -------- /pic Command --------


@bot.slash_command(name="pic", description="Search for images by query")
async def pic(inter: disnake.CommandInteraction, query: str):
    await inter.response.defer(ephemeral=True)

    urls = await serpapi_search_images(query, num=10)
    if not urls:
        return await inter.followup.send("No images found.", ephemeral=True)

    # Save browsing state
    user_sessions[inter.user.id] = {"urls": urls, "idx": 0, "query": query}

    # Make view with buttons
    view = disnake.ui.View()
    view.add_item(disnake.ui.Button(
        label="Prev", style=disnake.ButtonStyle.primary, custom_id="prev"))
    view.add_item(disnake.ui.Button(
        label="Next", style=disnake.ButtonStyle.primary, custom_id="next"))
    view.add_item(disnake.ui.Button(label="Confirm",
                  style=disnake.ButtonStyle.success, custom_id="confirm"))

    embed = build_embed(urls[0], query, 0, len(urls))
    await inter.followup.send(embed=embed, view=view, ephemeral=True)

# -------- Button Interaction --------


@bot.listen("on_button_click")
async def handle_buttons(inter: disnake.MessageInteraction):
    user_id = inter.user.id
    session = user_sessions.get(user_id)
    if not session:
        return await inter.response.send_message("Session expired.", ephemeral=True)

    urls = session["urls"]
    idx = session["idx"]
    query = session["query"]

    cid = inter.component.custom_id

    if cid == "prev":
        idx = (idx - 1) % len(urls)
    elif cid == "next":
        idx = (idx + 1) % len(urls)
    elif cid == "confirm":
        # Confirm posts public embed
        embed = disnake.Embed(title=f"Image for: {query}")
        embed.set_image(url=urls[idx])
        await inter.response.send_message(embed=embed, ephemeral=False)
        return

    # Update stored index
    session["idx"] = idx

    # Edit ephemeral message with new image
    new_embed = build_embed(urls[idx], query, idx, len(urls))
    await inter.response.edit_message(embed=new_embed, view=inter.message.components[0].view, ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Bot connected: APP ID: {bot.application_id}; Name: {bot.user.name}")

# -------- Run Bot --------
bot.run(BOT_TOKEN)
