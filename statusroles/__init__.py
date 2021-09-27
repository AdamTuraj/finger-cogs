from .statusroles import StatusRoles


async def setup(bot):
    statusroles = StatusRoles(bot)

    bot.add_cog(statusroles)
    await statusroles.set_cache()
