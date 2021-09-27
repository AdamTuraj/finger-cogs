from redbot.core import commands


class WordConverter(commands.Converter):
    def __init__(self):
        self.max_chars = 128

    async def convert(self, ctx: commands.Converter, arg: str):
        if len(arg) > self.max_chars:
            raise commands.BadArgument(
                f"A required status text can't be more then {self.max_chars} characters due to maximum status lengths."
            )

        return arg.lower()
