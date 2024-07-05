import os
import shutil
import pathlib
import pickle

import discord
from discord.ext import commands

import consts
import metadata
import signup
import views

intents = discord.Intents.default()
intents.message_content = True
intents.guild_scheduled_events = True

bot = commands.Bot(command_prefix='!', intents=intents)

def su_path(guild: discord.Guild, su_id: str):
    return consts.DATA_DIR / str(guild.id) / su_id

def create_guild(guild: discord.Guild):
    (consts.DATA_DIR / str(guild.id)).mkdir()

def delete_guild(guild: discord.Guild):
    shutil.rmtree(consts.DATA_DIR / str(guild.id))

@bot.event
async def on_guild_join(guild: discord.Guild):
    create_guild(guild)

@bot.event
async def on_guild_remove(guild: discord.Guild):
    delete_guild(guild)

@bot.command()
async def reset_guild(ctx):
    try:
        delete_guild(ctx.guild)
    except:
        pass
    create_guild(ctx.guild)
    await ctx.send("Server data was successfully reset.")

@bot.command()
async def create_sign_up(ctx, su_id, description):
    path = su_path(ctx.guild, su_id)

    # create directory
    try:
        path.mkdir()
    except FileExistsError:
        await ctx.send("Sign-up already exists.")
        return

    # write metadata
    (path / consts.META_FILE).write_bytes(pickle.dumps(
        metadata.Metadata(su_id, description))
    )

    # touch history
    (path / consts.HIST_FILE).touch()

    # response
    await ctx.send("Created sign-up `{}`.".format(su_id))

@bot.command()
async def delete_sign_up(ctx, su_id):
    path = su_path(ctx.guild, su_id)

    if not path.exists():
        await ctx.send("Sign-up does not exist.")
        return

    # delete event directory
    shutil.rmtree(path)

    # response
    await ctx.send("Deleted sign-up `{}`.".format(su_id))

@bot.command()
async def get_sign_ups(ctx):
    # get event ids from directory names
    paths = list((consts.DATA_DIR / str(ctx.guild.id)).iterdir())
    su_ids = ["\n* `{}`".format(child.parts[-1]) for child in (consts.DATA_DIR / str(ctx.guild.id)).iterdir()]

    if len(paths) == 0:
        await ctx.send("There are no sign-ups.")
        return

    outs = []
    for path in paths:
        meta = pickle.loads((path / consts.META_FILE).read_bytes())
        outs.append("\n* `{}` on {} channels ({})".format(
            path.parts[-1],
            len(meta.channels),
            "open" if (path / consts.SIGN_FILE).exists() else "closed",
        ))

    # response
    await ctx.send("Sign-ups:{}".format("".join(outs)))

@bot.command()
async def add_channel_to_sign_up(ctx, su_id):
    path = su_path(ctx.guild, su_id)

    if not path.exists():
        await ctx.send("Sign-up does not exist.")
        return

    if (path / consts.SIGN_FILE).exists():
        await ctx.send("Cannot modify open sign-up.")
        return

    # update metadata
    meta = pickle.loads((path / consts.META_FILE).read_bytes())
    meta.channels.add(ctx.channel.id)
    (path / consts.META_FILE).write_bytes(pickle.dumps(meta))

    # response
    await ctx.send("This channel has been added to sign-up `{}`.".format(su_id))

@bot.command()
async def remove_channel_from_sign_up(ctx, su_id):
    path = su_path(ctx.guild, su_id)

    if not path.exists():
        await ctx.send("Sign-up does not exist.")
        return

    if (path / consts.SIGN_FILE).exists():
        await ctx.send("Cannot modify open sign-up.")
        return

    # update metadata
    meta = pickle.loads((path / consts.META_FILE).read_bytes())
    try:
        meta.channels.remove(ctx.channel.id)
    except KeyError:
        await ctx.send("This channel is not in sign-up `{}`.".format(su_id))
        return
    (path / consts.META_FILE).write_bytes(pickle.dumps(meta))

    # response
    await ctx.send("This channel has been removed from sign-up `{}`.".format(su_id))

@bot.command()
async def open_sign_up(ctx, su_id):
    path = su_path(ctx.guild, su_id)

    if not path.exists():
        await ctx.send("Sign-up does not exist.")
        return

    if (path / consts.SIGN_FILE).exists():
        await ctx.send("Sign-up is already open.")
        return

    # open metadata
    with (path / consts.META_FILE).open("rb") as f:
        meta = pickle.load(f)
        view = views.SignUpView()

        # send sign up message to all channels
        msgs = []
        for chn in meta.channels:
            try:
                msgs.append(await ctx.guild.get_channel(chn).send(meta.description, view=view))
            except (discord.HTTPException, discord.Forbidden):
                pass

        # save messages for updates in sign up file
        (path / consts.SIGN_FILE).write_bytes(pickle.dumps(signup.SignUp(set(msg.id for msg in msgs))))

        fails = len(meta.channels) - len(msgs)

    # response
    if fails == 0:
        await ctx.send("Opened sign-up successfully.")
    else:
        await ctx.send("Opened sign-up with {} failures.".format(fails))

@bot.command()
async def close_sign_up(ctx, su_id):
    path = su_path(ctx.guild, su_id)

    if not path.exists():
        await ctx.send("Sign-up does not exist.")
        return

    if not (path / consts.SIGN_FILE).exists():
        await ctx.send("Sign-up is already closed.")
        return

    # TODO read, perform lottery, update messages, and add to history
    (path / consts.SIGN_FILE).unlink()

    # response
    await ctx.send("Closed sign-up successfully.")

if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if token is not None:
        bot.run(token)

