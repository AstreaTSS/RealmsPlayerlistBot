import discord, os, traceback
import asyncio, logging
from discord.ext import commands
from datetime import datetime
import cogs.utils.universals as univ

bot = commands.Bot(command_prefix='!?', fetch_offline_members=True)
bot.remove_command("help")

log = logging.getLogger('authentication')
log.setLevel(logging.ERROR)

@bot.event
async def on_ready():

    if bot.init_load == True:
        bot.config = {}
        bot.gamertags = {}
        bot.pastebins = {}

        bot.load_extension("cogs.config_fetch")
        while bot.config == {}:
            await asyncio.sleep(0.1)

        cogs_list = ["cogs.eval_cmd", "cogs.general_cmds", "cogs.mod_cmds", "cogs.playerlist"]

        for cog in cogs_list:
            bot.load_extension(cog)

        print('Logged in as')
        print(bot.user.name)
        print(bot.user.id)
        print('------\n')

        activity = discord.Activity(name = 'over some Bedrock Edition Realms', type = discord.ActivityType.watching)
        await bot.change_presence(activity = activity)
    else:
        utcnow = datetime.utcnow()
        time_format = utcnow.strftime("%x %X UTC")

        await univ.msg_to_owner(bot, f"Reconnected at {time_format}!")

    bot.init_load = False
    
@bot.check
async def block_dms(ctx):
    return ctx.guild is not None

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandInvokeError):
        original = error.original
        if not isinstance(original, discord.HTTPException):
            await univ.error_handle(bot, error, ctx)
    elif isinstance(error, (commands.ConversionError, commands.UserInputError, commands.CommandOnCooldown)):
        await ctx.send(error)
    elif isinstance(error, commands.CheckFailure):
        if ctx.guild != None:
            await ctx.send("You do not have the proper permissions to use that command.")
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        await univ.error_handle(bot, error, ctx)

@bot.event
async def on_error(event, *args, **kwargs):
    try:
        raise
    except Exception as e:
        await univ.error_handle(bot, e)

bot.init_load = True
bot.run(os.environ.get("MAIN_TOKEN"))
