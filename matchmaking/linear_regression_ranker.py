from cachetools.func import ttl_cache
from typing import Callable, List, Dict
from discord.channel import TextChannel

from numpy import matrix
from sklearn.linear_model import LinearRegression
from statistics import stdev, mean

from matchmaking.match_finder import Match
from matchmaking.game_data import GameData

@ttl_cache(maxsize=128, ttl=600) # 10 minutes
async def get_ranker(channel: TextChannel) -> Callable:
    """
    This function returns a 'ranker' function. It is meant to be used
    by matchmaker, e.g. `get_next_match(..., get_ranker(...))`, and it
    is only this complex so we can capture the channel in the closure. 
    """
    @ttl_cache(maxsize=128, ttl=600) # 10 minutes
    async def rank(matches: List[Match]):
        scores = await __get_scores(channel)
        def mean_balance(match: Match) -> float:
            (team_one, team_two) = match
            avg_one = mean([scores[p.member.id] for p in team_one])
            avg_two = mean([scores[p.member.id] for p in team_two])
            return abs(avg_one - avg_two)

        matches.sort(key=mean_balance)
    return rank

async def __get_scores(channel: TextChannel) -> Dict[int, float]:
    data = await GameData.fetch(channel) 
    model = LinearRegression().fit(
      __get_training_data(data),
      __get_target_values(data),
    )

    scores = model.coef_[0]
    average = mean(scores)
    std_dev = stdev(scores)

    player_scores = {}
    for i, player in enumerate(data.get_all_players()):
        player_scores[player] = (scores[i] - average) / std_dev
    return player_scores

def __get_training_data(data: GameData) -> matrix:
    foo = []
    players = data.get_all_players()
    for game in data.games:
        bar = []
        for player in players:
            bar.append(game.get_player_team_modifier(player))
        foo.append(bar)

    return matrix(foo)

def __get_target_values(data: GameData) -> matrix:
    return matrix([[g.get_percent_difference()] for g in data.games]) 