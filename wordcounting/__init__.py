from .wordcounting import WordCounting

__red_end_user_data_statement__ = (
    "This cog stores your data only if you were the last to count. ",
    "This data is to check if you double count.",
)


async def setup(bot):
    wordcounting = WordCounting(bot)
    bot.add_cog(wordcounting)

    await wordcounting.initialize()
