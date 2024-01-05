import discord
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Discord API
intents = discord.Intents.default()
intents.emojis_and_stickers = True
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

def chat(messages):
    res = requests.post(f'{os.getenv("OLLAMA_URL")}/api/chat', json={"model": os.getenv("OLLAMA_MODEL"), "stream": False, "messages": messages})
    if res.status_code == 200:
        return res.json()['message']['content']
    else:
        return False

async def send_long_message(channel, message):
    if len(message) > 2000:
        newline_index = message[:2000].rfind("\n")
        if newline_index == -1:
            newline_index = message[:2000].rfind(" ")
            if newline_index == -1:
                newline_index = 2000

        await channel.send(message[:newline_index])
        await send_long_message(channel, message[newline_index:])
    else:
        await channel.send(message)

@tree.command(name="ask", description=f"Ask me a question", guild=discord.Object(id=os.getenv("DISCORD_GUILD_ID")))
async def on_ask(interaction, question: str):
    await interaction.response.defer(thinking=True)
    chat_response = chat([{"role": "user", "content": question}])
    if chat_response:
        await interaction.followup.send(f"__Question: {question}__")
        await send_long_message(interaction.channel, chat_response)
    else:
        await interaction.followup.send(f"Could not process question: {question}")

@tree.command(name="chat", description=f"Start a chat", guild=discord.Object(id=os.getenv("DISCORD_GUILD_ID")))
async def on_chat(interaction):
    thread = await interaction.channel.create_thread(name=f"Chat with {client.user.display_name}", auto_archive_duration=60, reason="Started a discord-ollama chat")
    await thread.add_user(interaction.user)
    await thread.send(f"Hello! I am {client.user.display_name}, a chatbot using the {os.getenv('OLLAMA_MODEL')} model. Use /bye to end the chat.")
    await interaction.response.send_message(f"Chat started! <#{str(thread.id)}>", ephemeral=True)

@tree.command(name="bye", description=f"End a chat", guild=discord.Object(id=os.getenv("DISCORD_GUILD_ID")))
async def on_bye(interaction):
    if interaction.channel.name == f"Chat with {client.user.display_name}":
        await interaction.response.send_message("Goodbye :)")
        await interaction.channel.remove_user(interaction.user)
    else:
        await interaction.response.send_message(f"You are not in a chat with {client.user.display_name}!", ephemeral=True)
        return

@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=os.getenv("DISCORD_GUILD_ID")))
    print("Discord-ollama is ready")

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    if message.channel.name == f"Chat with {client.user.display_name}":
        messages = []
        oldest_skipped = False
        async for message in message.channel.history(limit=100, oldest_first=True):
            if not oldest_skipped:
                oldest_skipped = True
                continue
                
            if message.author == client.user:
                messages.append({"role": "assistant", "content": message.content})
            else:
                messages.append({"role": "user", "content": message.content})
        
        chat_response = chat(messages)
        if chat_response:
            await send_long_message(message.channel, chat_response)
        else:
            await message.channel.send(f"Could not process message: {message.content}")

client.run(os.getenv("DISCORD_TOKEN"))
print("Discord-ollama stopped")