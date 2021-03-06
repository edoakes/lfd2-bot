from unittest.mock import AsyncMock, patch
from datetime import datetime
from random import choice, randint
from string import digits
from typing import Callable, List

from aiounittest import AsyncTestCase
from discord import Member, Status, Colour
from discord import TextChannel, VoiceChannel
from discord.ext.commands.bot import Bot
from discord.embeds import Embed

from models.lobby import Lobby
from utils.usage_exception import UsageException
from matchmaking.game_data import Game, GameData, Team
from matchmaking.linear_regression_ranker import get_ranker
from matchmaking.random_shuffler import get_shuffler


def id() -> str:
    return int("".join(choice(digits) for _ in range(10)))


def channel(name: str = "", topic: str = "") -> TextChannel:
    channel = AsyncMock(spec=TextChannel)
    channel.id = id()
    channel.name = name
    channel.topic = topic
    channel.mention = id()
    return channel


def vchannel(participants: List[Member]) -> VoiceChannel:
    vchannel = AsyncMock(spec=VoiceChannel)
    vchannel.id = id()
    vchannel.members = participants
    return vchannel


def bot() -> Bot:
    bot = AsyncMock(spec=Bot)
    return bot


def member(status: Status = Status.online) -> Member:
    member = AsyncMock(spec=Member)
    member.id = id()
    member.display_name = id()
    member.mention = id()
    member.bot = None
    member.status = status
    return member


async def game_data(_channel) -> GameData:
    return GameData(
        [
            Game(
                datetime.today(),
                Team([id() for _ in range(4)], randint(1000, 3000)),
                Team([id() for _ in range(4)], randint(1000, 3000)),
            )
            for _ in range(5)
        ]
    )


def embed(self, mention: bool = False, title: str = None) -> Embed:
    embed = AsyncMock(Embed)
    return embed


class TestLobby(AsyncTestCase):
    async def test_add_remove(self):
        lobby = Lobby(bot(), channel())
        await lobby.add(player_one := member())
        assert len(lobby.players) == 1

        await lobby.add(player_two := member(), player_one)
        assert len(lobby.players) == 2

        await lobby.remove(player_one)
        assert len(lobby.players) == 1

        await lobby.remove(player_two)
        assert len(lobby.players) == 0

    async def test_full_lobby(self):
        lobby = Lobby(bot(), channel())
        await lobby.ready(first := member())
        assert not lobby.is_ready()
        for _ in range(7):
            await lobby.ready(member())
        assert lobby.is_ready()

        await lobby.add(alternate := member())
        with self.assertRaises(UsageException):
            await lobby.ready(alternate)

        await lobby.remove(first)
        assert not lobby.is_ready()

        await lobby.ready(alternate)
        assert lobby.is_ready()

        with self.assertRaises(UsageException):
            await lobby.ready(first)

    async def test_leavers(self):
        lobby = Lobby(bot(), channel())
        await lobby.add(author := member())
        await lobby.add(leaver := member(), author)

        # Removal by others does not prevent re-add
        await lobby.remove(leaver, author)
        assert not lobby.has_left_before(leaver)
        await lobby.add(leaver, author)

        # Leaving prevents re-add
        await lobby.remove(leaver)
        with self.assertRaises(UsageException):
            await lobby.add(leaver, author)
        await lobby.add(leaver)

    async def test_ready_unready(self):
        lobby = Lobby(bot(), channel())
        await lobby.add(player := member())

        await lobby.ready(player)
        assert lobby.ready_count() == 1

        await lobby.unready(player)
        assert lobby.ready_count() == 0

        await lobby.remove(player)

        await lobby.ready(player)
        assert lobby.ready_count() == 1

        await lobby.unready(player)
        assert lobby.ready_count() == 0

        await lobby.ready(player)
        assert lobby.ready_count() == 1

    async def test_lobby_embed(self):
        lobby = Lobby(bot(), channel())
        embed = lobby.get_lobby_message()
        assert embed.title == "Lobby (0)"
        assert embed.footer.text == "There are 8 spots remaining!"
        assert embed.colour == Colour.orange()

        await lobby.add(player := member())
        embed = lobby.get_lobby_message()
        assert embed.title == "Lobby (1)"
        assert embed.footer.text == "There are 8 spots remaining!"
        assert embed.colour == Colour.orange()
        assert len(embed.fields) == 1
        assert embed.fields[0].name == "Alternates (1)"
        assert str(player.display_name) in embed.fields[0].value

        embed = lobby.get_lobby_message(mention=True)
        assert str(player.display_name) in embed.fields[0].value

        await lobby.ready(player)
        embed = lobby.get_lobby_message()
        assert embed.title == "Lobby (1)"
        assert embed.footer.text == "There are 7 spots remaining!"
        assert embed.colour == Colour.orange()
        assert len(embed.fields) == 1
        assert embed.fields[0].name == "Players (1)"
        assert str(player.display_name) in embed.fields[0].value

        embed = lobby.get_lobby_message(mention=True)
        assert str(player.mention) in embed.fields[0].value

        for _ in range(7):
            await lobby.ready(member())
        embed = lobby.get_lobby_message()
        assert embed.title == "Lobby (8)"
        assert "Use `?shuffle` or `?ranked`" in embed.footer.text
        assert embed.colour == Colour.green()
        assert len(embed.fields) == 1
        assert embed.fields[0].name == "Players (8)"

        await lobby.unready(player)
        embed = lobby.get_lobby_message()
        assert embed.title == "Lobby (8)"
        assert embed.footer.text == "There's one spot remaining!"
        assert embed.colour == Colour.orange()
        assert len(embed.fields) == 2
        assert embed.fields[0].name == "Players (7)"
        assert embed.fields[1].name == "Alternates (1)"

        await lobby.remove(player)
        embed = lobby.get_lobby_message()
        assert embed.title == "Lobby (7)"
        assert embed.footer.text == "There's one spot remaining!"
        assert embed.colour == Colour.orange()
        assert len(embed.fields) == 1
        assert embed.fields[0].name == "Players (7)"

        for _ in range(100):
            await lobby.add(member())
        embed = lobby.get_lobby_message()
        assert embed.title == "Lobby (107)"
        assert embed.footer.text == "There's one spot remaining!"
        assert embed.colour == Colour.orange()
        assert len(embed.fields) == 2
        assert embed.fields[1].name == "Alternates (100)"

        await lobby.ready(member())
        embed = lobby.get_lobby_message()
        assert embed.title == "Lobby (108)"
        assert "Use `?shuffle` or `?ranked`" in embed.footer.text
        assert embed.colour == Colour.green()
        assert len(embed.fields) == 2
        assert embed.fields[0].name == "Players (8)"
        assert embed.fields[1].name == "Alternates (100)"

    async def test_game_start_message(self):
        lobby = Lobby(bot(), ctx := channel())
        lobby.get_lobby_message = AsyncMock()
        for _ in range(8):
            await lobby.ready(member())
        lobby.get_lobby_message.assert_called_with(
            mention=True,
            title=f"Game starting in ({ctx.mention}))",
        )

    async def test_numbers(self):
        discord_bot = bot()
        discord_bot.get_all_channels.return_value = [
            vchannel(participants=[member(), member()]),
            vchannel(participants=[member()]),
        ]

        lobby_channel = channel()
        online = [member() for _ in range(7)]
        offline = [member(status=Status.offline) for _ in range(5)]
        lobby_channel.guild.members = online + offline
        lobby = Lobby(discord_bot, lobby_channel)
        await lobby.add(member())
        lobby_channel.reset_mock()
        await lobby.show_numbers()
        assert len(lobby_channel.send.call_args_list) == 1
        embed: Embed = lobby_channel.send.call_args_list[0].kwargs["embed"]
        assert embed.title == "These are some numbers for sure."
        assert len(embed.fields) == 4
        fields = embed.fields
        assert fields[0].name == "Online" and fields[0].value == "7"
        assert fields[1].name == "In Voice" and fields[1].value == "3"
        assert fields[2].name == "Joined" and fields[2].value == "1"
        assert fields[3].name == "Ready" and fields[3].value == "0"

    @patch("matchmaking.game_data.GameData.fetch", game_data)
    async def test_match_combinations(self):
        async def test_with_ordering(order: Callable):
            lobby = Lobby(bot(), channel())
            for _ in range(8):
                await lobby.ready(member())

            seen = set()
            for _ in range(35):  # 35 times: (8 choose 4) / 2
                (_, (one, two)) = await lobby.get_next_match(order)
                assert (one, two) not in seen
                assert (two, one) not in seen
                seen.add((one, two))
                seen.add((two, one))

            final = await lobby.get_next_match(order)
            assert final is None

        await test_with_ordering(get_shuffler())
        await test_with_ordering(get_ranker(channel()))

    async def test_broadcast(self):
        discord_bot = bot()
        discord_bot.get_all_channels.return_value = [
            lobby_channel := channel(
                name="lobby", topic="@broadcast(#dest1)\n@broadcast(#dest2)"
            ),
            dest_one := channel(name="dest1"),
            dest_two := channel(name="dest2"),
            misc_channel := channel(name="misc"),
        ]

        lobby = Lobby(discord_bot, lobby_channel)
        await lobby.broadcast_game_almost_full()
        assert dest_one.send.call_count == 1
        assert dest_two.send.call_count == 1
        assert misc_channel.send.call_count == 0
