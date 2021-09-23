from redbot.core import commands
from redbot.core.utils.chat_formatting import humanize_number as hn


class NumberChecker(commands.Converter):
    def __init__(self):
        # Change this to whatever you want
        self.max_number = 999999999
        self.min_number = 1

    async def convert(self, ctx: commands.Context, arg: int) -> int:
        if not arg.isnumeric():
            raise commands.BadArgument("You must include a valid number.")

        arg = int(arg)

        if arg > self.max_number:
            raise commands.BadArgument(
                f"You must include a number below {hn(self.max_number)}"
            )
        elif arg < self.min_number:
            raise commands.BadArgument(
                f"You must include a number above {hn(self.min_number)}"
            )

        return arg
