from .statusroles import StatusRoles

__red_end_user_data_statement__ = "This cog does not store any End User Data."


async def setup(bot):
    statusroles = StatusRoles(bot)

    bot.add_cog(statusroles)
    await statusroles.set_cache()
