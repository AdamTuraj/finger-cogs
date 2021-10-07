from .clashofclans import ClashOfClans

__red_end_user_data_statement__ = "This cog stores data only if set by the user. Your clan and account tags are the only data saved."


def setup(bot):
    bot.add_cog(ClashOfClans(bot))
