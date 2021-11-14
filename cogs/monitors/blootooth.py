from io import BytesIO
import aiohttp
import discord
from discord.ext import commands
from data.model.guild import Guild
from data.services.guild_service import guild_service
from utils.logger import logger
from utils.config import cfg
import random

class Blootooth(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending_channels = set()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return
        if message.guild.id != cfg.guild_id:
            return
        
        # with self.create_lock:
        channel = message.channel
        db_guild = guild_service.get_guild()
        blootooth_mappings = db_guild.nsa_mapping
        
        webhooks = blootooth_mappings.get(str(channel.id))
        if channel.id not in self.pending_channels and webhooks is None:
            self.pending_channels.add(channel.id)
            webhooks = await self.handle_new_channel(channel, db_guild)
            self.pending_channels.remove(channel.id)

        # choose one of the three webhooks randomly
        async with aiohttp.ClientSession() as session:
            the_webhook: discord.Webhook = discord.Webhook.from_url(random.choice(webhooks), session=session)
            # send message to webhook
            message_body = await self.prepare_message_body(message)
            await the_webhook.send(**message_body, allowed_mentions=discord.AllowedMentions(users=False, everyone=False, roles=False))
    
    async def handle_new_channel(self, channel: discord.TextChannel, db_guild: Guild):
        # we have not seen this channel yet; let's create a channel in the Blootooth server
        # and create 3 new webhooks.
        # store the webhooks in the database.
        logger.info(f"Detected new channel {channel.name} ({channel.id})")
        guild: discord.Guild = self.bot.get_guild(db_guild.nsa_guild_id)
        category = discord.utils.get(guild.categories, name=channel.category.name)
        
        if category is None:
            category = await guild.create_category(name=channel.category.name)
        blootooth_channel = await category.create_text_channel(name=channel.name)
        webhooks = []
        for i in range(1):
            webhooks.append((await blootooth_channel.create_webhook(name=f"Webhook {blootooth_channel.name} {i}")).url)
        guild_service.set_nsa_mapping(channel.id, webhooks)
        
        logger.info(f"Added new webhooks for channel {channel.name} ({channel.id}:" + "\n" + '\n'.join(webhooks))
        return webhooks

    async def prepare_message_body(self, message: discord.Message):
        member = message.author
        body = {
            "username": str(member),
            "avatar_url": member.display_avatar,
            "embeds": message.embeds or discord.utils.MISSING,
            "files": [discord.File(BytesIO(await file.read()), filename=file.filename) for file in message.attachments]
        }
        
        footer=f"\n\n[Link to message]({message.jump_url}) | **{member.id}**"
        content = message.content
        for mention in message.raw_role_mentions:
            content = content.replace(f"<@&{mention}>", f"`@{message.guild.get_role(mention)}`")

        characters_left = 2000 - len(content) - len(footer) - 3
        if characters_left <= 0:
            content = content[:2000 - len(footer) - 3] + "..."
            
        body["content"] = f"{content}{footer}"
        return body

def setup(bot):
    bot.add_cog(Blootooth(bot))
