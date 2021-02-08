# War 2 analysis: going through partner clans and for all check
# last 25 battles, how many are war, and show win ratio, etc.
import sys
import datetime

from decouple import config

import db
import crlib as cr
import requests

import spreadsheet
from utils import log, err

# don't run CR API queries; don't save to Google sheets; print report to stdout
REPORT_DEBUG = False
REPORT_HOURS = [16, 18, 20, 8]


class ClanData:
    def __init__(self):
        self.battles_won = 0
        self.battles_played = 0


# The stats for a single player, war day won, lost, 
class PlayerStats:
    def __init__(self):
        self.id = None
        self.name = ""
        self.battles_won = 0
        self.battles_played = 0
        self.boat_attacks = 0
        # only the last 25 games are available!!, this is true if first game is after war day start
        self.limited_info = False


# determines war day date from the battle timestamp
def _get_war_day(dt, formatted=True):
    if dt.time() < datetime.time(10):
        res = (dt - datetime.timedelta(days=1))
    else:
        res = dt
    if formatted:
        return res.strftime("%Y-%m-%d")
    else:
        return res


def _get_war_start_prefix():
    today = datetime.datetime.utcnow()
    # before 10 am gmt look for the previous day :)
    today = today - datetime.timedelta(hours=10)
    timestamp = today.strftime("%Y%m%d")
    if today.isoweekday == 1:  # Monday, start of river race -> we look at 9:30
        timestamp += "T0930"
    else:
        timestamp += "T1000"
    return timestamp


# parses datetime format of the CR API
def _parse_cr_date(datetime_string):
    return datetime.datetime.strptime(datetime_string, '%Y%m%dT%H%M%S.%fZ')


def _save_battle(player, cr_timestamp, battles, won):
    dt = _parse_cr_date(cr_timestamp)
    war_day = _get_war_day(dt)
    db.save_battle(player.id, dt, war_day, battles, battles if won else 0, 0)


# Per player gather war battles, and update clan level player stats
def populate_war_games(clan_tag, player_tag, war_start_time, player):
    def get_towers_count(t):
        return (1 if "kingTowerHitPoints" in t and t["kingTowerHitPoints"] else 0) + \
               (len(t["princessTowersHitPoints"]) if "princessTowersHitPoints" in t else 0)

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
        # player might have been in a different clan during the war battle,
        # need to check for that
        if (battle_type == "riverRaceDuel"
            or battle_type == "riverRaceDuelColosseum"
            or battle_type == "riverRacePvP"
            or battle_type == "boatBattle") \
                and b["team"][0]["clan"]["tag"] == "#" + clan_tag:

            if battle_type == "riverRaceDuel" or battle_type == "riverRaceDuelColosseum":
                # we assume that the player that fewer towers at the end of the battle won the whole thing
                player_towers = get_towers_count(b["team"][0])
                opponent_towers = get_towers_count(b["opponent"][0])
                game_count = len(b["team"][0]["cards"]) / 8

                if war_start_time < b["battleTime"]:
                    if player_towers > opponent_towers:  # won the duel
                        player[player_tag].battles_won += game_count
                    player[player_tag].battles_played += game_count

                _save_battle(player[player_tag], b["battleTime"], game_count, player_towers > opponent_towers)
            elif battle_type == "riverRacePvP":
                defender_crown = b["team"][0]["crowns"] or 0
                opponent_crown = b["opponent"][0]["crowns"] or 0
                if war_start_time < b["battleTime"]:
                    if defender_crown > opponent_crown:  # won the battle
                        player[player_tag].battles_won += 1
                    player[player_tag].battles_played += 1

                _save_battle(player[player_tag], b["battleTime"], 1, defender_crown > opponent_crown)
            else:  # boatBattle
                if b["boatBattleSide"] != "defender":
                    if war_start_time < b["battleTime"]:
                        player[player_tag].battles_played += 1
                        player[player_tag].boat_attacks += 1
                    _save_battle(player[player_tag], b["battleTime"], 1, False)


# Iterate through clan members, collect clan level stats, incomplete games, player stats
def get_player_stats(ct, war_start_time, persistent_run):
    players = dict()

    try:
        for pt in cr.clan_member_tags(ct):
            if pt not in players:
                players[pt] = PlayerStats()
                players[pt].name = cr.get_player_name(pt)
                if persistent_run:
                    players[pt].id = db.get_player_id(pt, players[pt].name)
            populate_war_games(ct, pt, war_start_time, players)
    except Exception as e:
        err('Error loading player data, check API access and clan tag: ' + str(e))
    return players


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


# returns the cutout date for the report
# current logic: returns previous Sunday (always guaranteed to be at least one day ago)
def get_first_report_date():
    dt = datetime.datetime.utcnow()
    if dt.isoweekday == 1:
        return (dt - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    else:
        return (dt - datetime.timedelta(days=dt.weekday() + 1)).strftime("%Y-%m-%d")


# returns a text for posting on Discord
def get_notification_message():
    def get_player_mention(discord_id, name, is_in_clan, is_mini):
        res = ''
        if discord_id is not None:
            if is_mini:
                res = '**' + name + '** by '
            res += '<@' + str(discord_id) + '>'
        else:
            res = '**' + name + '**'
        if not is_in_clan:
            res += ' *(not in clan)*'
        return res

    message_template = """
Stats as of %s (%d hours before the war day end):  
**%d** players played %d games (%s%% of maximum 200); win rate is **%s%%**  
%s
    """.strip()
    now = datetime.datetime.utcnow()
    war_day = _get_war_day(now, False)
    war_day_formatted = _get_war_day(now)
    day_stats = db.get_war_day_stats(war_day_formatted)
    player_stats = db.get_war_day_player_stats(war_day_formatted)
    if not day_stats:
        return None

    if day_stats[0][1]:
        participation_rate = str(round(100 * day_stats[0][1] / 200, 2))
    else:
        participation_rate = 0
    if day_stats[0][1]:
        win_rate = str(round(100 * day_stats[0][2] / day_stats[0][1], 2))
    else:
        win_rate = 0

    players_report = "Players who didn't finish their war yet:  \n"
    if player_stats:
        for player in player_stats:
            players_report += '  ' + get_player_mention(player[1], player[0], player[2], player[3])
            if player[4] > 0:
                players_report += ' (' + str(4 - player[4]) + ')\n'
            else:
                players_report += '\n'
    else:
        players_report = '*Everybody played their battles. Great job!*'
    return message_template % (now.strftime('%H:%M:%S'),
                               round((datetime.datetime.combine(war_day + datetime.timedelta(days=1),
                                                                datetime.time(10, 0)) - now).seconds / 3600),
                               day_stats[0][0] or 0,
                               day_stats[0][1] or 0,
                               participation_rate,
                               win_rate,
                               players_report
                               )


def send_discord_message(url, message, report_url):
    requests.post(url,
                  headers={"Accept": "application/json", "Content-Type": "application/json", },
                  json={"content": message,
                        "embeds": [{
                            "title": "Full report",
                            "url": report_url
                        }]
                        })


def report():
    start_time = _get_war_start_prefix()

    if len(sys.argv) == 2 and sys.argv[1]:
        log('Running check for clan with tag ' + sys.argv[1])
        clan_tag = sys.argv[1]
        persistent_run = False
    else:
        log('Updating database and exporting default clan with tag ' + config('CLAN_TAG'))
        clan_tag = config('CLAN_TAG')
        persistent_run = True

    players = None
    if not REPORT_DEBUG:
        players = get_player_stats(clan_tag, start_time, persistent_run)
        if players:
            log('Stats loaded, %d players found' % len(players))
        else:
            return

        if persistent_run:
            db.mark_leavers([players[p].id for p in players if players[p].id is not None])
            log('Marked players no longer in clan')
    else:
        log('Report debug mode is ON')

    if persistent_run:
        cutout_date = get_first_report_date()
        log('Report cutout date: ' + cutout_date)
        out = db.get_report(cutout_date)
        if out is not None:
            if not REPORT_DEBUG:
                try:
                    spreadsheet.export_to_sheet(out)
                    log('Report exported')
                except Exception as e:
                    err('Cannot export report: ' + str(e))
            else:
                print(out)

            # for testing purposes, sending out notification only at 8 o'clock
            if config('DISCORD_WEBHOOK') and datetime.datetime.utcnow().time().hour in REPORT_HOURS:
                log('Updating players notification ids')
                db.reset_notification_ids()
                try:
                    mapping = spreadsheet.get_notifications_mapping()
                    if mapping:
                        for record in mapping:
                            if len(record) > 1 and record[0] and record[1]:
                                db.set_player_notification_id(record[0].upper(), record[1],
                                                              bool(record[2]) if len(record) > 2 else False)
                except Exception as e:
                    err('Cannot update player mapping: ' + str(e))

                log('Sending notification')
                try:
                    send_discord_message(config('DISCORD_WEBHOOK'), get_notification_message(),
                                         'https://docs.google.com/spreadsheets/d/' + config('SPREADSHEET_ID'))
                except Exception as e:
                    err('Cannot send notification message: ' + str(e))
            else:
                if config('DISCORD_WEBHOOK'):
                    log('Notification is not scheduled this time')
                else:
                    log('No webhook url, skipping notification')

        else:
            log('Report is empty, possibly no database')
            if players is not None:
                print_who_has_incomplete_games(players)
                print_clan_war_day_stats(clan_tag, players)
    else:
        if players is not None:
            print_who_has_incomplete_games(players)
            print_clan_war_day_stats(clan_tag, players)

    log('Run finished')


report()
