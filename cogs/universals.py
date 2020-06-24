import discord, traceback

async def proper_permissions(ctx):
    permissions = ctx.author.guild_permissions
    return (permissions.administrator or permissions.manage_messages)
    
async def error_handle(bot, error, ctx = None):
    error_str = ''.join(traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__))

    await msg_to_owner(bot, error_str)

    if ctx != None:
        await ctx.send("An internal error has occured. The bot owner has been notified.")

async def msg_to_owner(bot, string):
    application = await bot.application_info()
    owner = application.owner
    await owner.send(f"{string}")

async def user_from_id(bot, guild, user_id):
    user = guild.get_member(user_id)
    if user == None:
        try:
            user = await bot.fetch_user(user_id)
        except discord.NotFound:
            user = None

    return user