from datetime import timedelta

from discord.ext import commands

class TimeDelta(commands.Converter):
  async def convert(self, ctx, argument):
    try: 
      elems = (s.split() for s in argument.split(','))
      nice = {s[1] : int(s[0]) for s in elems}
      td = timedelta(**nice)
      return td
    except Exception:
      return commands.BadArgument(argument)
