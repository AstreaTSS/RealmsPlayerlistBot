<p align="center">
  <img src="https://cdn.discordapp.com/attachments/775915758588657664/916464019227947078/RealmsPlayerlistBotBanner.png" alt="Realm Playerlist Bot's Banner" width="700"/>
</p>

A bot that helps out owners of Minecraft: Bedrock Edition Realms by showing a log of players who have joined and left.

## The Playerlist
The playerlist/player log is a *very* in-demand feature. For a good reason, too - it's *kinda* a thing not many other bots do.

It looks something like this:

<p align="center">
  <img src="https://cdn.discordapp.com/attachments/775915758588657664/916460297961766923/Screenshot_2021-12-03_174426.png" alt="Picture of how the playerlist looks like"/>
</p>

<p align="center">
  <i>Replace the censored space with gamertags and you get the general gist of it.</i>
</p>

The list automatically runs/gets generated in a channel every hour, giving a useful hourly view of who all was on at what time, though there *is* also a command you can run to get who all was on in the last 24 hours.

The command can normally only be run by people with Manage Server permissions and is not meant to be seen by normal people - there *is* a command that can be run by everyone that allows you to view everyone currently online. Ask Astrea about that when adding the bot if you want it, since it is optional.

## Adding The Bot

If you wish to add this bot, [join my Support Server](https://discord.gg/NSdetwGjpK) and view the instructions in the realms-playerlist-bot-info. It isn't super simple to set up the bot, so...

Note that I'm not *always* available and may take a long time to get around to adding the bot to your server (though I'm *usually* quick enough), and there *may* be a couple of dealbreakers for you - I'd rather talk about those privately since they vary from person to person.

## Self-hosting Information

Honestly, *good luck*. This thing is *far* from simple to get everything working, requiring you to know the ins-and-outs of most of the libraries I use. The code *also* assumes you're using replit.com out of all sites (mainly because I can't afford hosting this on an actual server), so that makes things *even more* difficult.

But if you're willing to try... well, I won't leave a detailed guide here - just kinda poke around in the code and see what works. [`xbox-webapi-python`](https://github.com/OpenXbox/xbox-webapi-python) is worth looking if you're even considering it.

Environmental vars: `MAIN_TOKEN`, `DIRECTORY_OF_FILE`, `LOG_FILE_PATH`, `OPENXBL_KEY`, `DB_URL`, `BOT_COLOR`, `CLIENT_ID`, `CLIENT_SECRET`, `XAPI_TOKENS`, `CLIENT_ID`, `CLIENT_SECRET`, `XAPI_TOKENS`, `REDIS_URL`, `onami_NO_UNDERSCORE=true` (last one is optional but recommended)

## Links:

* [Join Support Server](https://discord.gg/NSdetwGjpK)
