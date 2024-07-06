import os
import shutil
import pathlib
import pickle

import discord
from discord.ext import commands

import consts
import metadata
import signup

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

async def get_member(guild, u_id):
    user = guild.get_member(u_id)
    return (await guild.fetch_member(u_id)) if user is None else user

async def get_channel(guild, c_id):
    chn = guild.get_channel(c_id)
    return (await guild.fetch_channel(c_id)) if chn is None else chn

class SignUpView(discord.ui.View):
    def __init__(self, su_id, description):
        super().__init__()
        self.su_id = su_id
        self.description = description

    async def update_messages(self, messages, users, guild):
        # format users
        user_strs = []
        for u_id in users:
            user_strs.append("\n* {}".format((await get_member(guild, u_id)).mention))

        if len(user_strs) == 0:
            out = "{}\nBe the first to sign up!".format(self.description)
        else:
            out = "{}\nSigned up:{}".format(self.description, "".join(user_strs))

        # edit all messages TODO parallel
        for c_id, m_id in messages:
            await (await (await get_channel(guild, c_id)).fetch_message(m_id)).edit(
                content=out,
                view=self,
            )

    @discord.ui.button(label="Sign Up")
    async def sign_up(self, intrxn, button):
        path = su_path(intrxn.guild, self.su_id) / consts.SIGN_FILE

        try:
            sign_up = pickle.loads(path.read_bytes())
        except KeyError:
            # TODO fix
            return

        sign_up.users.add(intrxn.user.id)
        path.write_bytes(pickle.dumps(sign_up))

        # update each message with list of signed-up users
        await self.update_messages(sign_up.messages, sign_up.users, intrxn.guild)

        await intrxn.response.defer()

    @discord.ui.button(label="Cancel")
    async def cancel(self, intrxn, button):
        path = su_path(intrxn.guild, self.su_id) / consts.SIGN_FILE

        try:
            sign_up = pickle.loads(path.read_bytes())
        except KeyError:
            # TODO fix
            return

        sign_up.users.discard(intrxn.user.id)
        path.write_bytes(pickle.dumps(sign_up))

        # update each message with list of signed-up users
        await self.update_messages(sign_up.messages, sign_up.users, intrxn.guild)

        await intrxn.response.defer()

@bot.event
async def on_guild_join(guild: discord.Guild):
    create_guild(guild)

@bot.event
async def on_guild_remove(guild: discord.Guild):
    delete_guild(guild)

@bot.command()
async def pbot_help(ctx):
    await ctx.send(
        "* `pbot_help`: prints this message\n"
        "* `reset_server`: resets all server data\n"
        "* `create_sign_up`: creates a new sign up with supplied id\n"
        "* `delete_sign_up`: deletes a sign up by the supplied id\n"
        "* `get_sign_ups`: lists all sign ups for the server with some info\n"
        "* `add_channel_to_sign_up`: adds the channel the command is executed in to the sign up with supplied id\n"
        "* `remove_channel_from_sign_up`: removes the channel the command is executed in from the sign up with supplied id\n"
        "* `open_sign_up`: opens a sign up by id and posts message to all of the sign up's channels\n"
        "* `close_sign_up`: closes a sign up by id (currently just deletes list of signed up users)\n"
        "* `update_sign_up_messages`: forces all sign up messages associated with the id to be updated (needed if bot goes offline)\n"
    )

@bot.command()
async def reset_server(ctx):
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
        await ctx.send("Sign-up is must be closed.")
        return

    # open metadata
    meta = pickle.loads((path / consts.META_FILE).read_bytes())
    view = SignUpView(su_id, meta.description)

    # send sign up message to all channels
    msgs = []
    for chn in meta.channels:
        try:
            msgs.append((chn, (await (await get_channel(ctx.guild, chn)).send(meta.description, view=view)).id))
        except (discord.HTTPException, discord.Forbidden):
            pass

    print(msgs)

    # save messages for updates in sign up file
    (path / consts.SIGN_FILE).write_bytes(pickle.dumps(signup.SignUp(set(msg for msg in msgs))))

    fails = len(meta.channels) - len(msgs)

    # response
    if fails == 0:
        await ctx.send("Opened sign-up successfully.")
    else:
        await ctx.send("Opened sign-up with {} failures.".format(fails))

@bot.command()
async def update_sign_up_messages(ctx, su_id):
    path = su_path(ctx.guild, su_id)

    if not path.exists():
        await ctx.send("Sign-up does not exist.")
        return

    if not (path / consts.SIGN_FILE).exists():
        await ctx.send("Sign-up must be open.")
        return

    # open metadata
    meta = pickle.loads((path / consts.META_FILE).read_bytes())
    view = SignUpView(su_id, meta.description)

    # open sign up
    sign_up = pickle.loads((path / consts.SIGN_FILE).read_bytes())

    # update messages
    await view.update_messages(sign_up.messages, sign_up.users, ctx.guild)

    # response
    await ctx.send("Sign-up messages updated.")


@bot.command()
async def close_sign_up(ctx, su_id):
    path = su_path(ctx.guild, su_id)

    if not path.exists():
        await ctx.send("Sign-up does not exist.")
        return

    if not (path / consts.SIGN_FILE).exists():
        await ctx.send("Sign-up must be open.")
        return

    # TODO read, perform lottery, update messages, and add to history
    (path / consts.SIGN_FILE).unlink()

    # response
    await ctx.send("Closed sign-up successfully.")

if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if token is not None:
        bot.run(token)

