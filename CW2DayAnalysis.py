# War 2 analysis: going through partner clans and for all check
# last 25 battles, how many are war, and show win ratio, etc.

from datetime import datetime, timedelta

import crlib as cr
import requests

riverClanTags = ["JP8VUC", "2Q9JYY9J", cr.clan_tag, "29R0YQ09", "8UUP909U"]


class ClanData:
    def __init__(self):
        self.battles_won = 0
        self.battles_played = 0


# The stats for a single player, war day won, lost, 
class PlayerStats:
    def __init__(self):
        self.name = ""
        self.battles_won = 0
        self.battles_played = 0
        self.boat_attacks = 0
        # only the last 25 games are available!!, this is true if first game is after war day start
        self.limited_info = False


def get_war_start_prefix():
    today = datetime.utcnow()
    # before 10 am gmt look for the previous day :)
    today = today - timedelta(hours=10)
    timestamp = today.strftime("%Y%m%d")
    if today.isoweekday == 1:  # Monday, start of river race -> we look at 9:30
        timestamp += "T0930"
    else:
        timestamp += "T1000"
    return timestamp


# Per player gather war battles, and update clan level player stats
def populate_war_games(player_tag, war_start_time, player):
    r2 = requests.get("https://api.clashroyale.com/v1/players/%23" + player_tag + "/battlelog",
                      headers={"Accept": "application/json", "authorization": cr.auth},
                      params={"limit": 100})
    battles = r2.json()
    # Types are: (NOT complete, there may be many others)
    # boatBattle
    # casual1v1
    # casual2v2
    # challenge
    # clanMate
    # clanMate2v2
    # friendly
    # None
    # PvP
    # riverRaceDuel
    # riverRacePvP
    # riverRaceDuelColosseum
    # get the last timestamp (battles are newest first)
    if len(battles) > 0:
        b = battles[-1]
        if war_start_time < b["battleTime"]:  # this should be the oldest game
            player[player_tag].limited_info = True

    for b in battles:
        battle_type = b["type"]
        if ((battle_type == "riverRaceDuel"
             or battle_type == "riverRaceDuelColosseum"
             or battle_type == "riverRacePvP"
             or battle_type == "boatBattle") and war_start_time < b["battleTime"]):
            # print (json.dumps(b, indent = 2))
            # print("%s %s"%(b["battleTime"], b["type"]))

            # opponent -> crowns (compare???), team [0] crowns???

            if battle_type == "riverRaceDuel" or battle_type == "riverRaceDuelColosseum":
                defender_crown = b["team"][0]["crowns"]
                opponent_crown = b["opponent"][0]["crowns"]
                # print("%s %s by %s  %s:%s"%(b["battleTime"], b["type"],
                #       cr.getPlayerName(playerTag),defenderCrown, opponentCrown))
                # print("Team Card length:%s" % len(b["team"][0]["cards"]))
                game_count = len(b["team"][0]["cards"]) / 8
                if defender_crown > opponent_crown:  # won the duel
                    player[player_tag].battles_won += game_count
                player[player_tag].battles_played += game_count
            elif battle_type == "riverRacePvP":
                defender_crown = b["team"][0]["crowns"]
                opponent_crown = b["opponent"][0]["crowns"]
                if defender_crown > opponent_crown:  # won the battle
                    player[player_tag].battles_won += 1
                player[player_tag].battles_played += 1

            else:  # boatBattle
                player[player_tag].battles_played += 1
                player[player_tag].boat_attacks += 1


# Iterate through clan members, collect clan level stats, incomplete games, player stats
def get_player_stats(ct, war_start_time):
    ps = dict()

    for m in cr.clan_member_tags(ct):
        if m not in ps:
            ps[m] = PlayerStats()
        populate_war_games(m, war_start_time, ps)
    return ps


# Print clan's statistics for the war day (participant numbers, win ratio)
def print_clan_war_day_stats(ct, player_stats):
    cd = ClanData()
    clan_name = cr.get_clan_name(ct)
    for key, value in player_stats.items():
        cd.battles_won += value.battles_won
        cd.battles_played += value.battles_played

    if cd.battles_played == 0:
        win_ratio = 0
    else:
        win_ratio = round(100 * cd.battles_won / cd.battles_played, 2)

    print("%s: %s war battles played, %s won (%s%% win rate), %s members participated" %
          (clan_name, cd.battles_played, cd.battles_won, win_ratio, len(player_stats)))


# Print the players and the number of war games completed during the active war two day
def print_who_has_incomplete_games(player_stats):
    for key, value in sorted(player_stats.items(), reverse=True, key=lambda item: item[1].battles_played):
        if value.limited_info:
            caveat_msg = "25+ games since war start"
        else:
            caveat_msg = ""
        print("%s: %s %s" % (cr.get_player_name(key), int(value.battles_played), caveat_msg))


start_time = get_war_start_prefix()
# warStartTime = "20210125T0930"
# warStartTime = "20210127T1000"
print("War day start is: %s" % start_time)

pss = get_player_stats(cr.clan_tag, start_time)
print_who_has_incomplete_games(pss)
