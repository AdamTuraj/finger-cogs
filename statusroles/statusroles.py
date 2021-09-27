import discord
from redbot.core import Config, commands

from .converters import WordConverter


class StatusRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=183948923980)

        self.srs_cache = {}

        self.default_guild = {"srs": {}}
        self.config.register_guild(**self.default_guild)

    async def set_cache(self):
        self.srs_cache = await self.config.all_guilds()

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        new_status = after.activity

        if (
            not new_status
            or after.bot
            or new_status.type != discord.ActivityType.custom
            or before.activity == after.activity
        ):
            return

        srs = self.srs_cache.get(after.guild.id)

        if not srs:
            return

        for required_word, role_id in srs["srs"].items():
            if required_word in str(after.activity).lower():
                role = discord.Object(role_id)
                try:
                    await after.add_roles(
                        role, reason="Member has a set word to get this role."
                    )
                except discord.Forbidden:
                    continue

    @commands.group(name="sr")
    @commands.admin_or_permissions(manage_guild=True)
    async def sr_group(self, ctx):
        """The main group for the status roles settings."""

    @sr_group.command()
    async def add(self, ctx, role: discord.Role, *, requiredText: WordConverter):
        """Add a status role."""

        async with self.config.guild(ctx.guild).srs() as srs:
            srs[requiredText] = role.id

        await self.set_cache()

        await ctx.send(
            f"You will now get the role {role.name} if someone has the text `{requiredText}` in their status."
        )

    @sr_group.command()
    async def remove(self, ctx, text: WordConverter = None):
        """Removes a status role."""

        async with self.config.guild(ctx.guild).srs() as srs:
            result = srs.pop(text, None)

        if not result:
            raise commands.BadArgument(f"The text `{text}` has not been added yet.")

        role = ctx.guild.get_role(result)

        await self.set_cache()

        await ctx.send(
            f"You will no longer get the role `{role.name}` with the text {text}."
        )

    @sr_group.command()
    async def list(self, ctx):
        """Lists all of the status roles."""

        srs = await self.config.guild(ctx.guild).srs()

        if not srs:
            await ctx.send("This server has no status roles.")
            return

        role_text = ""

        for text, role_id in srs.items():
            role = ctx.guild.get_role(role_id)

            role_text += f"**{text}**, {role.mention} "

        embed = discord.Embed(description=role_text, colour=await ctx.embed_colour())

        embed.set_author(
            name=f"Status roles for {ctx.guild.name}", icon_url=ctx.guild.icon_url
        )

        await ctx.send(embed=embed)
