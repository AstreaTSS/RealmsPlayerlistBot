<p align="center">
  <img src="https://cdn.discordapp.com/attachments/775932004985208853/846987950058635274/BedrockRealmBotBanner.png" alt="Realm Plus Bot's Banner" width="700"/>
</p>

A bot that helps out owners of Minecraft: Bedrock Edition Realms, otherwise known as Realm Plus Realms.

## Features

There are three things the bot can do: keep a log of players who have joined and left, verify the gamertags of users, and deal with season roles and their management.

### Playerlist
The playerlist/player log is the most in-demand feature. For a good reason, too - it's *kinda* a thing not many other bots do.

It looks something like this:

<p align="center">
  <img src="https://cdn.discordapp.com/attachments/775915758588657664/914348347719032832/Screenshot_2021-11-27_215120.png" alt="Picture of how the playerlist looks like"/>
</p>

<p align="center">
  <i>Replace the censored space with gamertags and you get the general gist of it.</i>
</p>

The list automatically runs/gets generated in a channel every hour, giving a useful hourly view of who all was on wt what time, though there *is* also a command you can run to get who all was on in the last 24 hours.

The command can normally only be run by people with Manage Server permissions and is not meant to be seen by normal people - there *is* a command that can be run by everyone that allows you to view everyone currently online. Ask Astrea about that when adding the bot if you want it, since it is optional.

### Gamertag Verification

Using a simple command, you can check if a gamertag is an actual, legit gamertag. It isn't *too* useful since it can't find out the gamertag of a player or the like, but it *can* be used for verifying that a gamertag a user provided is at least legitimate.

### Season Role Management

Some realms have season roles for their seasons. It's often a *huge* hassle adding them to everyone at the end of the season, so the bot provides a way to do that. There's *also* a little command that allows users to see every member who has a certain season role.

## Adding The Bot

If you wish to add this bot, [join my Support Server](https://discord.gg/NSdetwGjpK) and DM me (Astrea) - I'll talk about how to set it up and all, since it isn't *that* simple.

Note that I'm not *always* available and may take a long time to get around to adding the bot to your server (though I'm *usually* quick enough), and there *may* be a couple of dealbreakers for you - I'd rather talk about those in DMs since they vary from person to person.

## Self-hosting Information

Honestly, *good luck*. This thing is *far* from simple to get everything working, requiring you to know the ins-and-outs of most of the libraries I use. The code *also* assumes you're using replit.com out of all sites (mainly because I can't afford hosting this on an actual server), so that makes things *even more* difficult.

But if you're willing to try... well, I won't leave a detailed guide here - just kinda poke around in the code and see what works. [`xbox-webapi-python`](https://github.com/OpenXbox/xbox-webapi-python) is worth looking if you're even considering it.

Environmental vars: `MAIN_TOKEN`, `DIRECTORY_OF_FILE`, `LOG_FILE_PATH`, `OPENXBL_KEY`, `CONFIG_URL`, `BOT_COLOR`, `CLIENT_ID`, `CLIENT_SECRET`, `XAPI_TOKENS`, `CLIENT_ID`, `CLIENT_SECRET`, `XAPI_TOKENS`, `JISHAKU_NO_UNDERSCORE=true` (last one is optional but recommended)

## Links:

* [Join Support Server](https://discord.gg/NSdetwGjpK)
* [![Run on Repl.it](https://repl.it/badge/github/Se/GenericRealmBot)](https://repl.it/github/Astrea49/GenericRealmBot)
