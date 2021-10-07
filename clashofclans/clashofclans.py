import asyncio
import logging
import math
from datetime import datetime
from enum import Enum
from typing import Dict, Optional

import aiohttp
import discord
from redbot.core import Config, commands
from redbot.core.utils.menus import (menu, next_page, prev_page,
                                     start_adding_reactions)
from redbot.core.utils.predicates import ReactionPredicate

from .converters import EmojiConverter, TagConverter, UnlinkTagConverter

logger = logging.getLogger("red.finger_cogs.clashofclans")


async def has_account(ctx) -> bool:
    account = await ctx.cog.config.user(ctx.author).accounts()

    if not account:
        raise commands.UserFeedbackCheckFailure(
            f"You must have an account to run this command. You can do this with `{ctx.prefix}account link <playerTag>`."
        )

    return True


class TroopTypes(Enum):
    elixir = "Elixir Troops"
    dark = "Dark Elixir Troops"
    siege = "Siege Machines"
    pet = "Pets"
    builder = "Builder Base Troops"
    hero = "Heroes"
    espell = "Elixir Spells"
    dspell = "Dark Elixir Spells"


class ClashOfClans(commands.Cog):
    BASE_URL = "https://api.clashofclans.com/v1/"

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=93103499209)

        self.townhalls = {
            1: "https://static.wikia.nocookie.net/clashofclans/images/f/fd/Town_Hall1.png/",
            2: "https://static.wikia.nocookie.net/clashofclans/images/7/7d/Town_Hall2.png/",
            3: "https://static.wikia.nocookie.net/clashofclans/images/d/dd/Town_Hall3.png/",
            4: "https://static.wikia.nocookie.net/clashofclans/images/e/e7/Town_Hall4.png/",
            5: "https://static.wikia.nocookie.net/clashofclans/images/a/a3/Town_Hall5.png/",
            6: "https://static.wikia.nocookie.net/clashofclans/images/5/52/Town_Hall6.png/",
            7: "https://static.wikia.nocookie.net/clashofclans/images/7/75/Town_Hall7.png/",
            8: "https://static.wikia.nocookie.net/clashofclans/images/f/fa/Town_Hall8.png/",
            9: "https://static.wikia.nocookie.net/clashofclans/images/e/e0/Town_Hall9.png/",
            10: "https://static.wikia.nocookie.net/clashofclans/images/5/5c/Town_Hall10.png/",
            11: "https://static.wikia.nocookie.net/clashofclans/images/9/96/Town_Hall11.png/",
            12: "https://static.wikia.nocookie.net/clashofclans/images/c/c7/Town_Hall12-1.png/",
            13: "https://static.wikia.nocookie.net/clashofclans/images/9/98/Town_Hall13-1.png/",
            14: "https://static.wikia.nocookie.net/clashofclans/images/e/e0/Town_Hall14-1.png/",
        }

        # If this is outdated create a pr or issue
        self.all_troops = {
            "barbarian": "elixir",
            "archer": "elixir",
            "goblin": "elixir",
            "giant": "elixir",
            "wall breaker": "elixir",
            "balloon": "elixir",
            "wizard": "elixir",
            "healer": "elixir",
            "dragon": "elixir",
            "p.e.k.k.a": "elixir",
            "miner": "elixir",
            "electro dragon": "elixir",
            "yeti": "elixir",
            "dragon rider": "elixir",
            "minion": "dark",
            "hog rider": "dark",
            "valkyrie": "dark",
            "golem": "dark",
            "witch": "dark",
            "lava hound": "dark",
            "bowler": "dark",
            "ice golem": "dark",
            "headhunter": "dark",
            "wall wrecker": "siege",
            "battle blimp": "siege",
            "stone slammer": "siege",
            "siege barracks": "siege",
            "log launcher": "siege",
            "l.a.s.s.i": "pet",
            "electro owl": "pet",
            "mighty yak": "pet",
            "unicorn": "pet",
            "raged barbarian": "builder",
            "sneaky archer": "builder",
            "boxer giant": "builder",
            "beta minion": "builder",
            "bomber": "builder",
            "cannon cart": "builder",
            "night witch": "builder",
            "drop ship": "builder",
            "super p.e.k.k.a": "builder",
            "hog glider": "builder",
            "baby dragon": ["elixir", "builder"],
            "barbarian king": "hero",
            "archer queen": "hero",
            "grand warden": "hero",
            "royal champion": "hero",
            "battle machine": "hero",
            "lightning spell": "espell",
            "healing spell": "espell",
            "rage spell": "espell",
            "jump spell": "espell",
            "freeze spell": "espell",
            "clone spell": "espell",
            "invisibility spell": "espell",
            "poison spell": "dspell",
            "earthquake spell": "dspell",
            "haste spell": "dspell",
            "skeleton spell": "dspell",
            "bat spell": "dspell",
        }

        self.non_army_emoji_names = {
            "gold": "Gold",
            "elixir": "Elixir",
            "dark elixir": "Dark Elixir",
        }

        self.millnames = ["", "K", "M", "B"]

        self.default_controls = {"⬅️": prev_page, "➡️": next_page}

        self.default_headers: Dict = {"Authorization": ""}

        self.session = aiohttp.ClientSession()

        self.issue_response = "There was an issue with the request. Please check the logs to find the error."

        self.default_global = {"token": None, "emojis": self.gen_default_emojis()}
        self.default_user = {"accounts": [], "clan": None}

        self.config.register_global(**self.default_global)
        self.config.register_user(**self.default_user)

        self.emoji_loop = self.bot.loop.create_task(self.initialize())

    def gen_default_emojis(self):
        emojis = {troop_name: None for troop_name in self.all_troops.keys()}

        for item_name in self.non_army_emoji_names.keys():
            emojis[item_name] = None

        return emojis

    async def update_headers(self):
        token = await self.config.token()
        if not token:
            return

        self.default_headers["Authorization"] = "Bearer " + token

    async def initialize(self):
        await self.bot.wait_until_ready()
        await self.generate_emojis()
        await self.update_headers()

    async def generate_emojis(self):
        emojis = await self.config.emojis()

        self.emojis = {}

        for emoji_name, emoji_id in emojis.items():
            emoji = self.bot.get_emoji(emoji_id) if emoji_id else None
            fallback = self.non_army_emoji_names.get(emoji_name) or emoji_name

            self.emojis[emoji_name] = {"emoji": emoji, "fallback": fallback}

    def cog_unload(self):
        if self.emoji_loop:
            self.emoji_loop.cancel()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.session.close())

    async def red_delete_data_for_user(self, requester, user_id):
        for user in await self.config.all_users():
            if user_id == user:
                await self.config.user_from_id(user_id).clear()

    @commands.group(name="clash")
    async def clash(self, ctx):
        """The group for most clash of clans cog commands."""

    @clash.command(aliases=["profile"])
    async def player(self, ctx, playerTag: Optional[TagConverter]):
        """Displays the stats for you, or someone else.

        **playerTag**, leaving this blank will show you your linked account.
        """

        tags = await self.config.user(ctx.author).accounts()

        if playerTag is None:
            if not tags:
                raise commands.BadArgument(
                    f"Please enter a valid player tag or link your account using `{ctx.prefix}account link`."
                )

            playerTags = tags
        else:
            playerTags = [playerTag]

        if len(playerTags) == 1:
            data = await self.request(f"players/%23{playerTags[0]}")

            if not data:
                await ctx.send(self.issue_response)
                return

            await ctx.send(
                embed=await self.generate_user_embed(data, await ctx.embed_colour())
            )
            return

        embeds = []

        for page_num, tag in enumerate(playerTags, start=1):
            data = await self.request(f"players/%23{tag}")

            if not data:
                await ctx.send(self.issue_response)
                return

            embed = await self.generate_user_embed(data, await ctx.embed_colour())

            embed.set_footer(text=f"User {page_num} of {len(tags)}")

            embeds.append(embed)

        await menu(ctx, embeds, self.default_controls)

    @clash.command(aliases=["unit"])
    async def army(self, ctx, playerTag: Optional[TagConverter]):
        """Get the levels of troops, spells and heros of you, or someone else.

        **playerTag**, leaving this blank will show you your linked account.
        """

        tags = await self.config.user(ctx.author).accounts()

        if playerTag is None:
            if not tags:
                raise commands.BadArgument(
                    f"Please enter a valid clan tag or link your clan using `{ctx.prefix}clash linkclan`."
                )

            playerTags = tags

        else:
            playerTags = [playerTag]

        embed = discord.Embed(colour=await ctx.embed_colour())

        for tag in playerTags:
            data = await self.request(f"players/%23{tag}")

            embed.set_author(
                name=f"Troop levels for {data['name']}",
                url=f"https://link.clashofclans.com/en?action=OpenPlayerProfile&tag=%23{tag}",
            )

            army = {
                "elixir": {},
                "dark": {},
                "siege": {},
                "pet": {},
                "builder": {},
                "espell": {},
                "dspell": {},
            }

            dark_baby_dragon = False

            for troop in data["troops"]:
                try:
                    troop_type = self.all_troops[troop["name"].lower()]
                except KeyError:
                    continue

                if troop["name"] == "Baby Dragon":
                    if not dark_baby_dragon:
                        troop_type = "elixir"
                        dark_baby_dragon = True
                    else:
                        troop_type = "builder"

                army[troop_type][troop["name"]] = {
                    "level": troop["level"],
                    "maxLevel": troop["maxLevel"],
                }

            for spell in data["spells"]:
                spell_type = self.all_troops[spell["name"].lower()]

                army[spell_type][spell["name"]] = {
                    "level": spell["level"],
                    "maxLevel": spell["maxLevel"],
                }

            for type, troops in army.items():
                text = " ".join(
                    f"**{self.get_emoji(troop_name)}** `{troop_data['level']}/{troop_data['maxLevel']}`"
                    for troop_name, troop_data in troops.items()
                )
                if text:
                    embed.add_field(
                        name=f"__**{TroopTypes[type].value}**__",
                        value=text,
                        inline=False,
                    )

        await ctx.send(embed=embed)

    @clash.command()
    async def clan(self, ctx, clanTag: Optional[TagConverter]):
        """Displays the stats for the given clan tag.

        **clanTag**, leaving this blank will show you your linked clan.
        """

        tag = await self.config.user(ctx.author).clan()

        if clanTag is None:
            if not tag:
                raise commands.BadArgument(
                    f"Please enter a valid clan tag or link your clan using `{ctx.prefix}clash linkclan`."
                )

            clanTag = clanTag

        data = await self.request(f"clans/%23{clanTag}")

        if not data:
            await ctx.send(self.issue_response)
            return

        embed = discord.Embed(
            description=f"**Level {data['clanLevel']}, Members {data['members']}, {data['clanPoints']} Trophies, {data['clanVersusPoints']} versus trophies\n\n{data['description']}",
            colour=await ctx.embed_colour(),
        )

        embed.set_author(
            name=f"{data['name']} ({data['tag']})",
            url=f"https://link.clashofclans.com/en?action=OpenClanProfile&tag=%23{clanTag}",
            icon_url=data["badgeUrls"]["small"],
        )

        embed.set_thumbnail(url=data["badgeUrls"]["large"])

        tags = "\n".join(f"- {tag['name']}" for tag in data["labels"])

        leader = ""
        for member in data["memberList"]:
            if member["role"] == "leader":
                leader = member
                break

        tieslosses = ""

        if data["isWarLogPublic"]:
            tieslosses = f", {data['warLosses']} lost, {data['warTies']} ties"

        embed.add_field(
            name="__**Clan Info**__",
            value=f"**Tags**\n{tags}\n\n**Clan Leader**\n[{leader['name']} ({leader['tag']})](https://link.clashofclans.com/en?action=OpenPlayerProfile&tag=%23{leader['tag'][1:]})\n\n**Location**\n{data['location']['name']}\n\n**Requirements**\n{'Invite Only' if data['type'] == 'inviteOnly' else 'Open'}\n{data['requiredTrophies']} trophies required\n{data['requiredVersusTrophies']} versus trophies required\nTownhall {data['requiredTownhallLevel']} required\n\n**War Log**\n{'Public' if data['isWarLogPublic'] else 'Private'}",
        )

        embed.add_field(
            name="__**War and League**__",
            value=f"**War League**\n{data['warLeague']['name']}\n**War Stats**\n{data['warWins']} won{tieslosses}\n**Win Streak**\n{data['warWinStreak']}",
            inline=False,
        )

        await ctx.send(embed=embed)

    @clash.command(aliases=["members"])
    async def clanmembers(self, ctx, clanTag: Optional[TagConverter]):
        """See clan members of a choosen clan.

        **clanTag**, leaving this blank will show you your linked clan.
        """

        tag = await self.config.user(ctx.author).clan()

        if clanTag is None:
            if not tag:
                raise commands.BadArgument(
                    f"Please enter a valid clan tag or link your clan using `{ctx.prefix}account linkclan`."
                )

            clanTag = tag

        data = await self.request(f"clans/%23{clanTag}")

        if not data:
            await ctx.send(self.issue_response)
            return

        members = "\n".join(
            f"`{member['tag']}` {member['name']}" for member in data["memberList"]
        )

        embed = discord.Embed(
            title="Tag             Name",
            description=members,
            color=await ctx.embed_colour(),
        )
        embed.set_author(
            name=f"Members of {data['name']} ({data['tag']})",
            url=f"https://link.clashofclans.com/en?action=OpenClanProfile&tag=%23{clanTag}",
        )

        await ctx.send(embed=embed)

    @clash.command(aliases=["donations"])
    async def clandonations(self, ctx, clanTag: Optional[TagConverter]):
        """Shows donation data from most donated to least of the clan.

        **clanTag**, leaving this blank will show you your linked clan.
        """

        tag = await self.config.user(ctx.author).clan()

        if clanTag is None:
            if not tag:
                raise commands.BadArgument(
                    f"Please enter a valid clan tag or link your clan using `{ctx.prefix}account linkclan`."
                )

            clanTag = tag

        data = await self.request(f"clans/%23{clanTag}")

        if not data:
            await ctx.send(self.issue_response)
            return

        donation_data = {
            member["donations"]: {
                "name": member["name"],
                "received": member["donationsReceived"],
                "donated": member["donations"],
            }
            for member in data["memberList"]
        }

        sorted_keys = sorted(list(donation_data), reverse=True)

        donation_description = ""

        for position, key in enumerate(sorted_keys, start=1):
            user_data = donation_data[key]
            donation_description += f"{position}   {user_data['donated']}   {user_data['received']}   {user_data['name']}\n"

        embed = discord.Embed(
            title="#    Don    Rec    Name",
            description=f"```{donation_description}```",
            colour=await ctx.embed_colour(),
        )
        embed.set_author(
            name=f"Top Donations of {data['name']} ({data['tag']})",
            url=f"https://link.clashofclans.com/en?action=OpenClanProfile&tag=%23{clanTag}",
        )

        await ctx.send(embed=embed)

    @clash.command(aliases=["war"])
    async def clanwar(self, ctx, clanTag: Optional[TagConverter]):
        """Shows current war statistics of choosen clan.

        **clanTag**, leaving this blank will show you your linked clan.
        """

        tag = await self.config.user(ctx.author).clan()

        if clanTag is None:
            if not tag:
                raise commands.BadArgument(
                    f"Please enter a valid clan tag or link your clan using `{ctx.prefix}account linkclan`."
                )

            clanTag = tag

        data = await self.request(f"clans/%23{clanTag}/currentwar")

        if not data:
            await ctx.send(self.issue_response)
            return

        if data["state"] == "notInWar":
            await ctx.send("This clan is not currently in a war.")
            return

        embed = discord.Embed(colour=await ctx.embed_colour())
        embed.set_author(
            name=f"Current war of {data['clan']['name']}",
            url=f"https://link.clashofclans.com/en?action=OpenClanProfile&tag=%23{clanTag}",
        )

        opponent_data = data["opponent"]

        embed.add_field(
            name="__**Opponent**__",
            value=f"[{opponent_data['name']}({opponent_data['tag']})](https://link.clashofclans.com/en?action=OpenClanProfile&tag=%23{opponent_data['tag'][1:]})",
            inline=False,
        )

        state = data["state"]

        timestamp = 0

        unformated_timestamp = (
            data["startTime"] if state == "preparation" else data["endTime"]
        )
        timestamp = str(
            datetime.strptime(unformated_timestamp, "%Y%m%dT%H%M%S.%fZ").timestamp()
        )

        state_text = f"{state.title()}\nTime until {'battle day' if state == 'preparation' else 'end of war'}: <t:{timestamp[:-2]}:R>"

        embed.add_field(
            name="__**War Info**__",
            value=f"**Team Size:** {data['teamSize']}\n**Attacks per Member:** {data['attacksPerMember']}\n\n**War State**\n{state_text}",
        )

        embed.add_field(
            name="__**War Stats**__",
            value=f"**Ally**\n{data['clan']['attacks']} Attacks\n{data['clan']['stars']} Stars\n{data['clan']['destructionPercentage']}% Destruction\n\n**Opponent**\n{data['opponent']['attacks']} Attacks\n{data['opponent']['stars']} Stars\n{data['opponent']['destructionPercentage']}% Destruction",
            inline=False,
        )

        await ctx.send(embed=embed)

    @clash.command(aliases=["token"])
    @commands.is_owner()
    async def settoken(self, ctx, token: str):
        """Sets the token required to make requests to the Clash of Clans API.

        You can request one at [The Clash of Clans developer page](http://developer.clashofclans.com).
        """

        show_verified_text = True

        await self.config.token.set(token)
        await self.update_headers()
        if ctx.channel.permissions_for(ctx.guild.me).manage_messages:
            await ctx.message.delete()
        else:
            show_verified_text = False

        await ctx.send(
            f"The authorization token has been updated. {'I have deleted your message to keep your token safe!' if show_verified_text else ''}"
        )

    @clash.command(aliases=["reset"])
    @commands.is_owner()
    async def resettoken(self, ctx):
        """Resets your API token."""

        msg = await ctx.send("Are you sure you want to reset your token?")
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS)

        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        await ctx.bot.wait_for("reaction_add", check=pred)

        await msg.delete()

        if not pred.result:
            await ctx.send("Reset cancelled, your token is still saved.")
            return

        await self.config.token.clear()
        await ctx.tick()

    @clash.command(aliases=["emoji"])
    @commands.is_owner()
    async def setemoji(self, ctx, emoji: discord.Emoji, *, emoji_name: EmojiConverter):
        """Set an emoji for a certain troop or thing.

        Check `[p]clash emojis` for what emojis you can set.
        """

        async with self.config.emojis() as emojis:
            emojis[emoji_name] = emoji.id

        await self.generate_emojis()
        await ctx.send(f"You have set the emoji {emoji} to {emoji_name}")

    @clash.command(aliases=["emojis"])
    @commands.is_owner()
    async def listemojis(self, ctx):
        """List all of the things you can set emojis to."""

        emojis = " ".join(f"`{emoji.title()}`" for emoji in self.emojis.keys())
        embed = discord.Embed(
            title="These are all of the emoji options",
            description=emojis,
            colour=await ctx.embed_colour(),
        )
        await ctx.send(embed=embed)

    @commands.group(name="account")
    async def account(self, ctx):
        """The group for account linking commands."""

    @account.command()
    @commands.check(has_account)
    async def list(self, ctx, user: discord.User = None):
        """View all of yours or someone elses clash accounts linked to their Discord account."""

        if user is None:
            user = ctx.author

        user_data = await self.config.user(user).all()

        account_text = ""
        for tag in user_data["accounts"]:
            data = await self.request(f"players/%23{tag}")
            account_text += f"[{data['name']} ({data['tag']})](https://link.clashofclans.com/en?action=OpenPlayerProfile&tag=%23{tag})\n\n"

        if not account_text:
            raise commands.BadArgument("This user has no accounts connected to them.")

        embed = discord.Embed(colour=await ctx.embed_colour())
        embed.set_author(
            name=f"{user.name} Connected Accounts", icon_url=user.avatar_url
        )

        if user_data["clan"]:
            clan_data = await self.request(f"clans/%23{user_data['clan']}")

            embed.add_field(
                name="Clan",
                value=f"[{clan_data['name']} ({clan_data['tag']})](https://link.clashofclans.com/en?action=OpenClanProfile&tag=%23{clan_data['tag']})",
                inline=False,
            )

        embed.add_field(name="Accounts", value=account_text, inline=False)

        await ctx.send(embed=embed)

    @account.command()
    async def link(self, ctx, tag: TagConverter):
        """Link your Clash of clans account to your Discord account."""

        data = await self.request(f"players/%23{tag}")
        if not data:
            await ctx.send(self.issue_response)
            return

        async with self.config.user(ctx.author).accounts() as tags:
            tags.append(tag)

        await ctx.send(f"Your Discord account has been linked with **{data['name']}**.")

    @account.command()
    async def unlink(self, ctx, tag: UnlinkTagConverter):
        """Unlink your Clash of clans account from your Discord account."""

        data = await self.request(f"players/%23{tag}")
        if not data:
            await ctx.send(self.issue_response)
            return

        async with self.config.user(ctx.author).accounts() as tags:
            tags.remove(tag)

        await ctx.send(
            f"Your Discord account has been unlinked from **{data['name']}**."
        )

    @account.command()
    async def linkclan(self, ctx, tag: TagConverter):
        """Link your Clash of clans clan to your Discord account."""

        playerTag = await self.config.user(ctx.author).accounts()

        if not playerTag:
            raise commands.BadArgument("You don't have an account linked.")

        data = await self.request(f"players/%23{playerTag[0]}")
        if not data:
            await ctx.send(self.issue_response)
            return

        clan = data.get("clan")
        if not clan:
            raise commands.BadArgument("You are not in a clan.")

        if clan["tag"][1:] != tag:
            raise commands.BadArgument("You are not in this clan.")

        await self.config.user(ctx.author).clan.set(tag)

        await ctx.send(f"Your Discord account has been linked to **{clan['name']}**.")

    @account.command()
    async def unlinkclan(self, ctx, tag: UnlinkTagConverter):
        """Unlink your Clash of clans clan from your Discord account."""

        data = await self.request(f"clans/%23{tag}")
        if not data:
            await ctx.send(self.issue_response)
            return

        await self.config.user(ctx.author).clan.clear()

        await ctx.send(
            f"Your Discord account has been unlinked from **{data['name']}**."
        )

    async def generate_user_embed(
        self, data: Dict, embed_colour: discord.Colour
    ) -> discord.Embed:

        townhall_image = self.townhalls[data["townHallLevel"]]

        embed = discord.Embed(
            description=f"**TH {data['townHallLevel']}, {data['trophies']} trophies, Level {data['expLevel']}**",
            colour=embed_colour,
        )
        embed.set_author(
            name=f"{data['name']} ({data['tag']})",
            url=f"https://link.clashofclans.com/en?action=OpenPlayerProfile&tag={data['tag'][1:]}",
            icon_url=self.townhalls[data["townHallLevel"]],
        )
        embed.set_thumbnail(url=townhall_image)

        embed.add_field(
            name="__**Current Season Stats**__",
            value=f"**Troops Donated**\n{data['donations']}\n**Troops Received**\n{data['donationsReceived']}\n**Attacks Won**\n{data['attackWins']}\n**Defenses Won**\n{data['defenseWins']}",
            inline=False,
        )

        clan = data.get("clan")
        if clan:
            embed.add_field(
                name="__**Clan**__",
                value=f"[**{clan['name']} ({clan['tag']})**](https://link.clashofclans.com/en?action=OpenClanProfile&tag=%23{clan['tag'][1:]})\n**Position**:\n{data['role'].capitalize()}",
                inline=False,
            )

        embed.add_field(
            name="__**Achievements**__",
            value=f"**Total Loot**\n{self.get_total_loot(data['achievements'])}\n**Best Trophies**\n{data['bestTrophies']} trophies",
        )

        heros = data.get("heroes")

        if heros:
            hero_text = "\n".join(
                f"**{self.get_emoji(hero['name'].lower())}** {hero['level']}"
                for hero in heros
            )

            embed.add_field(name="__**Heroes**__", value=hero_text, inline=False)

        return embed

    def millify(self, number: int):
        number = float(number)

        millidx = max(
            0,
            min(
                len(self.millnames) - 1,
                int(math.floor(0 if number == 0 else math.log10(abs(number)) / 3)),
            ),
        )

        return f"{number / 10 ** (3 * millidx):.2f}{self.millnames[millidx]}"

    def get_total_loot(self, achievements: Dict):
        achiev_names = {
            "Gold Grab": "gold",
            "Elixir Escapade": "elixir",
            "Heroic Heist": "dark",
        }
        loot = {"elixir": 0, "gold": 0, "dark": 0}

        for achiev in achievements:
            try:
                loot_type = achiev_names[achiev["name"]]
            except KeyError:
                continue

            loot[loot_type] = achiev["value"]

        return f"**{self.get_emoji('gold')}** {self.millify(loot['gold'])}, **{self.get_emoji('elixir')}** {self.millify(loot['elixir'])}, **{self.get_emoji('dark elixir')}** {self.millify(loot['dark'])}"

    def get_emoji(self, emoji_name: str):
        emoji = self.emojis.get(emoji_name.lower())
        if not emoji:
            return

        return emoji["emoji"] or emoji["fallback"].title()

    async def check_response_for_errors(self, response: aiohttp.ClientResponse):

        if response.status == 404:
            raise commands.BadArgument(
                f"{'Player' if 'players' in str(response.url) else 'Clan'} was not found."
            )
        elif response.status == 200:
            return True
        else:
            logger.warning(
                f"Request returned {response.status}.\nError info: {await response.json()}"
            )

    async def request(self, endpoint: str) -> Dict:
        async with self.session.get(
            self.BASE_URL + endpoint,
            headers=self.default_headers,
        ) as response:
            if not await self.check_response_for_errors(response):
                return False
            return await response.json()
