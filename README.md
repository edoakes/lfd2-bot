# lfd2-bot
A tool to help form lobbies for Left 4 Dead 2 within Discord channels

# Requirements

- Python 3.8^

## Python Modules
- discord
- pillow

Eventually I'll get a setup.py configured for all dependencies

# Getting Started
1. Clone the repository to your local machine
2. Install the required Python modules
3. Configure a test Discord bot using this tutorial https://discordpy.readthedocs.io/en/latest/discord.html

**Step 3 Details**
- Ensure you use a name unique to your user
- Create a copy of example.config.json as config.json and populate it with the key you get from the tutorial
- Send a discord admin your bot invite URL

4. Run the bot `DISCORD_TOKEN="<your secret token>" python bot.py `
5. (optional) Change the command prefix in `bot.py`, e.g. from `?` to `!` 

# Useful Debug Commands

**note: It's highly recommended to add some sort of unique identifier in `bot.py` to make sure not to kill/reload anyone elses bot**

`reload` - will reload the lobby cog without having to restart the bot. This is incredibly useful but will clear any variables within that cog

`disconnect` - kills the bot 



