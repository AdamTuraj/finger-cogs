from redbot.core import commands


class TagConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, arg: str):
        arg = arg.replace("#", "")

        return arg


class UnlinkTagConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, arg: str):
        arg = arg.replace("#", "")

        command = str(ctx.command)

        tags = (
            await ctx.cog.config.user(ctx.author).clan()
            if command == "unlinkclan"
            else await ctx.cog.config.user(ctx.author).accounts()
        )

        if arg not in tags:
            raise commands.BadArgument(
                f"You are not currently linked with this {'clan' if command == 'unlinkclan' else 'account'}."
            )

        return arg


class EmojiConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, arg: str):
        arg = arg.lower()

        if arg not in ctx.cog.emojis.keys():
            raise commands.BadArgument(
                f"Invalid emoji name. Please see `{ctx.prefix}clash emojis` to see the valid keys."
            )

        return arg
