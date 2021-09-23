import re
from typing import Union

import discord
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import humanize_number as hn

from .converters import NumberChecker


async def isenabled(ctx):
    channel = await ctx.cog.config.guild(ctx.guild).channel()

    if not channel:
        raise commands.UserFeedbackCheckFailure(
            "Word counting is currently disabled. ",
            "You must enable it to use this command.",
        )

    if channel := ctx.guild.get_channel(channel):
        return True

    raise commands.UserFeedbackCheckFailure(
        "The counting channel has been deleted. ",
        "You must change it to a valid channel to use this command.",
    )


class WordCounting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=387428934982398, force_registration=True
        )

        self.default_guild = {
            "channel": None,
            "next_number": 1,
            "ignore_failed": False,
            "last_user": None,
            "multi_count": False,
        }

        # If you ever change these next 3 variables,
        # make sure to add a space to the end
        # or it will not work properly.

        self.under20 = [
            "",
            "one ",
            "two ",
            "three ",
            "four ",
            "five ",
            "six ",
            "seven ",
            "eight ",
            "nine ",
            "ten ",
            "eleven ",
            "twelve ",
            "thirteen ",
            "fourteen ",
            "fifteen ",
            "sixteen ",
            "seventeen ",
            "eighteen ",
            "nineteen ",
        ]

        self.tens = [
            "",
            "",
            "twenty ",
            "thirty ",
            "forty ",
            "fifty ",
            "sixty ",
            "seventy ",
            "eighty ",
            "ninety ",
        ]

        # No one will probably surpass this
        self.suffixes = ["", "thousand ", "million ", "billion "]

        self.config.register_guild(**self.default_guild)

        self.data_cache = {}

    async def red_delete_data_for_user(self, requester, user_id):
        for guild, data in (await self.config.all_guilds()).copy().items():
            if data["last_user"] == user_id:
                await self.config.guild_from_id(guild).last_user.clear()

    async def update_cache(self, guild: discord.Guild):
        self.data_cache[guild.id] = await self.config.guild(guild).all()

    async def initialize(self):
        self.data_cache = await self.config.all_guilds()

    async def num2word(self, num: int):

        # Try not to mess this up, or the counting will be messed up

        split_three_digit = []
        while num:
            num, digits = divmod(num, 1000)
            split_three_digit.append(await self.digit_to_word(digits))

        suffixes = self.suffixes[: len(split_three_digit)]

        return "".join(
            f"{word}{suffixes[-count]}"
            for count, word in enumerate(reversed(split_three_digit), start=1)
        )[:-1]

    async def digit_to_word(self, num: int) -> str:
        if num < 20:
            return self.under20[num]

        if num < 100:
            tens, ones = divmod(num, 10)
            return f"{self.tens[tens]}{self.under20[ones]}"

        hundreds, rest = divmod(num, 100)

        return f"{self.under20[hundreds]}hundread {await self.digit_to_word(rest)}"

    async def generate_failed(
        self,
        user: Union[discord.User, discord.Member],
        guild: discord.Guild,
        failed_number: int,
        fail_message: str,
    ) -> discord.Embed:

        async with self.config.guild(guild).all() as current_data:
            current_data["next_number"] = 1
            current_data["last_user"] = None

        await self.update_cache(guild)

        embed = discord.Embed(
            title="The count got ruined!",
            description=(
                f"{user.mention} messed up the counting streak at ",
                f"**{failed_number} ({await self.num2word(failed_number)}).",
                f"**\nThe next number is now **1 (one).\n{fail_message}**",
            ),
            color=0xFF3C26,
        )
        embed.set_author(name=user.name, icon_url=user.avatar_url)
        embed.set_footer(text=guild.name, icon_url=guild.icon_url)
        return embed

    @commands.Cog.listener()
    async def on_message(self, message):

        guild = message.guild

        if (
            not guild
            or message.author.bot
            or await self.bot.cog_disabled_in_guild_raw("wordcounting", guild.id)
        ):
            return

        data = self.data_cache.get(guild.id)
        if not data:
            return

        if data["channel"] != message.channel.id:
            return

        if data["last_user"] == message.author.id and not data["multi_count"]:
            await message.channel.send(
                embed=await self.generate_failed(
                    message.author,
                    guild,
                    data["next_number"],
                    # You can put your own custom fail message here
                    "Next time don't count multiple times in a row.",
                )
            )
            return

        word = await self.num2word(data["next_number"])

        removed_characters = re.sub(r" and |-", " ", message.content.lower())

        if removed_characters == word:
            await message.add_reaction("✅")
            async with self.config.guild(guild).all() as current_data:
                current_data["next_number"] += 1
                current_data["last_user"] = message.author.id

            await self.update_cache(guild)
        elif data["ignore_failed"]:
            return
        else:
            await message.channel.send(
                embed=await self.generate_failed(
                    message.author,
                    guild,
                    data["next_number"],
                    # You can put your own custom fail message here
                    "Next time check your spelling.",
                )
            )

    @commands.group(name="wordcountset", aliases=["wcs"])
    @commands.admin_or_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def wordcountset(self, ctx):
        """Adjust all of the word counting settings."""

    @wordcountset.command(name="settings")
    async def wordcounting_settings(self, ctx):
        """Shows the servers word counting settings."""
        all_data = await self.config.guild(ctx.guild).all()

        guild = ctx.guild

        if channel := guild.get_channel(all_data["channel"]):
            channel = channel.mention
        else:
            channel = "None"

        embed = discord.Embed(
            title="Word Counting Settings", color=await ctx.embed_colour()
        )
        embed.set_author(name=guild.name, icon_url=guild.icon_url)
        embed.add_field(name="Channel:", value=channel, inline=True)
        embed.add_field(
            name="Ignore failed counting:",
            value=all_data["ignore_failed"],
            inline=False,
        )
        embed.add_field(
            name="Allow multi-count:", value=all_data["multi_count"], inline=False
        )

        await ctx.send(embed=embed)

    @wordcountset.command(name="channel")
    async def wordcounting_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the channel where the counting is done.

        If no channel is provided then it will disable word counting for the server.
        """
        if not channel and ctx.guild.id in self.data_cache:
            await self.config.guild(ctx.guild).channel.clear()
            await self.update_cache(ctx.guild)

            await ctx.send("Word counting is now disabled.")
            return

        await self.config.guild(ctx.guild).channel.set(channel.id)
        await self.update_cache(ctx.guild)
        await ctx.send(f"{channel.mention} has been set for word counting.")

    @wordcountset.command(name="ignorefailed")
    @commands.check(isenabled)
    async def wordcounting_ignorefailed(self, ctx, toggle: bool = None):
        """Toggle whether the bot should ignore incorrect numbers."""

        target_setting = (
            toggle
            if toggle is not None
            else await self.config.guild(ctx.guild).ignore_failed()
        )

        await self.config.guild(ctx.guild).ignore_failed.set(target_setting)
        await self.update_cache(ctx.guild)

        await ctx.send(
            f"Failed numbers will {'no longer' if not target_setting else 'now'} be ignored."
        )

    @wordcountset.command(name="multicount")
    @commands.check(isenabled)
    async def wordcounting_multi_count(self, ctx, toggle: bool = None):
        """Toggle wheter you should be able to count multiple numbers in a row."""

        target_setting = (
            toggle
            if toggle is not None
            else await self.config.guild(ctx.guild).ignore_failed()
        )

        await self.config.guild(ctx.guild).multi_count.set(target_setting)
        await self.update_cache(ctx.guild)

        await ctx.send(
            f"You can {'no longer' if not target_setting else 'now'} count multiple times in a row."
        )

    @wordcountset.command(name="setcount")
    @commands.check(isenabled)
    async def wordcounting_set_count(self, ctx, count: NumberChecker):
        """Set the number where counting should continue from.

        You must set the value between 999,999,999 and 1.
        """

        await self.config.guild(ctx.guild).next_number.set(count)
        await self.update_cache(ctx.guild)

        channel = await self.config.guild(ctx.guild).channel()
        channel = ctx.guild.get_channel(channel)

        embed = discord.Embed(
            title="Next Number Updated",
            description=f"The next number is now **{hn(count)} ({await self.num2word(count)})**.",
            color=await ctx.embed_colour(),
        )
        await channel.send(embed=embed)

        if channel != ctx.channel:
            await ctx.send(
                f"The next number has been updated to {hn(count)}. ",
                f"I have notified everyone counting in {channel.mention}.",
            )

    @wordcountset.command(name="resetcount")
    @commands.check(isenabled)
    async def wordcounting_reset_count(self, ctx):
        """Resets the number back to one."""

        await self.config.guild(ctx.guild).next_number.clear()
        await self.update_cache(ctx.guild)

        channel = await self.config.guild(ctx.guild).channel()
        channel = ctx.guild.get_channel(channel)

        embed = discord.Embed(
            title="Counting has been reset",
            description="The next number is now **1 (one)**.",
            color=await ctx.embed_colour(),
        )
        await channel.send(embed=embed)

        if channel != ctx.channel:
            await ctx.send(
                "Counting has been reset to 1. ",
                f"I have notified everyone counting in {channel.mention}.",
            )
