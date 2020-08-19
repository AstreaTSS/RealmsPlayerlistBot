import discord, traceback

async def proper_permissions(ctx):
    # checks if author has admin or manage guild perms or is the owner
    permissions = ctx.author.guild_permissions
    return (permissions.administrator or permissions.manage_guild
    or ctx.guild.owner.id == ctx.author.id)
    
async def error_handle(bot, error, ctx = None):
    # handles errors and sends them to owner
    error_str = error_format(error)

    await msg_to_owner(bot, error_str)

    if ctx != None:
        await ctx.send("An internal error has occured. The bot owner has been notified.")

async def msg_to_owner(bot, content):
    # sends a message to the owner
    owner = bot.owner
    string = str(content)

    str_chunks = string_split(string)

    for chunk in str_chunks:
        await owner.send(f"{chunk}")

def error_format(error):
    # simple function that formats an exception
    return ''.join(traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__))

def string_split(string):
    # simple function that splits a string into 1950-character parts
    return [string[i:i+1950] for i in range(0, len(string), 1950)]

async def user_from_id(bot, guild, user_id):
    user = guild.get_member(user_id)
    if user == None:
        try:
            user = await bot.fetch_user(user_id)
        except discord.NotFound:
            user = None

    return user