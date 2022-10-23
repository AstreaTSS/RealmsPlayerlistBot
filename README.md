<p align="center">
  <img src="https://cdn.discordapp.com/attachments/775915758588657664/916464019227947078/RealmsPlayerlistBotBanner.png" alt="Realm Playerlist Bot's Banner" width="700"/>
</p>

A bot that helps out owners of Minecraft: Bedrock Edition Realms by showing a log of players who have joined and left.

## The Playerlist
The playerlist/player log is a *very* in-demand feature. For a good reason, too - it's something not many other bots do.

It looks something like this:

<p align="center">
  <img src="https://cdn.discordapp.com/attachments/775915758588657664/916460297961766923/Screenshot_2021-12-03_174426.png" alt="Picture of how the playerlist looks like"/>
</p>

<p align="center">
  <i>Replace the censored space with gamertags and you get the general gist of it.</i>
</p>

The list automatically runs/gets generated in a channel every hour, giving a useful hourly view of who all was on at what time, though there *is* also a command you can run to get who all was on in the last 24 hours.

The command can normally only be run by people with Manage Server permissions and is not meant to be seen by normal people - there *is* a command that can be run by everyone that allows you to view everyone currently online, though.

## Premium

**Realms Playerlist Premium** allows for extra features that otherwise could not be provided by the bot without funding. While this is very basic for now, it is planned to expand heavily in the future.

There's only one feature right now, but it's probably the one most demanded for - a **live playerlist**! Basically, instead of making the bot send a summary of people on every hour, a live playerlist shows who joined and left a Realm every minute, basically making it a live join/leave logger.

It looks something like this (minus the obvious censoring):

<p align="center">
  <img src="https://user-images.githubusercontent.com/25420078/194965554-7e0b15a4-2186-4797-bd1d-9645c1caee79.png" alt="Preview on how the live playerlist looks like" height=420/>
</p>

This has a variety of uses, from statistical to moderation - it's really up to you what you do with this information. I know of one Realm owner who uses it both to narrow down subjects to a precise degree while also tracking active Realm times. Using Discord's search functionality (heavily suggest looking into that if you haven't use it, by the way), the possibilities are near endless.

Take a closer look at Premium [here.](https://github.com/Astrea49/RealmsPlayerlistBot/wiki/Playerlist-Premium-and-How-to-Get-It)

## Adding The Bot

If you wish to add this bot, just [use this guide on how to do so!](https://github.com/Astrea49/RealmsPlayerlistBot/wiki/Server-Setup)

## Self-hosting Information

Honestly, *good luck*. This thing is *far* from simple to get everything working, requiring you to know the ins-and-outs of most of the libraries I use. It can be a mess, and gathering the databases and servers needed even more so. There's also not much room for simplification here.

But if you're willing to try... well, I won't leave a detailed guide here - just kinda poke around in the code and see what works. [`xbox-webapi-python`](https://github.com/OpenXbox/xbox-webapi-python) is worth looking if you're even considering it.

## FAQ

There's a whole section in the wiki about this! Check it out [here](https://github.com/Astrea49/RealmsPlayerlistBot/wiki/FAQ).

## Links:

* [Bot Setup Guide](https://github.com/Astrea49/RealmsPlayerlistBot/wiki/Server-Setup)
* [Join Support Server](https://discord.gg/NSdetwGjpK)
* [Support me on Ko-fi](https://ko-fi.com/astrea49)
