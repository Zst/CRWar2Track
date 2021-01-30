import datetime


# determines war day date from the battle timestamp
def _get_war_day(dt):
    if dt.time() < datetime.time(9, 30) or (dt.isoweekday == 1 and dt.time() < datetime.time(10)):
        return (dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        return dt.strftime("%Y-%m-%d")


# parses datetime format of the CR API
def _parse_cr_date(datetime_string):
    return datetime.datetime.strptime(datetime_string, '%Y%m%dT%H%M%S.%fZ')


# marks players not listed in the `players_in_clan` list as the ones not currently in clan
def mark_leavers(players_in_clan):
    print("UPDATE player SET is_in_clan = false WHERE id NOT IN (%s)" % ','.join(players_in_clan))
    return None


# returns player id from the database; if record doesn't exist, creates it
def get_player_id(player_tag, player_name):
    # print("""
    #         INSERT INTO player (tag, name) VALUES ('%s', '%s')
    #         WHERE NOT EXISTS (
    #             SELECT 1
    #             FROM player
    #             WHERE tag = '%s'
    #         );
    #     """ % (player_tag, player_name.replace("'", "\\'"), player_tag))
    return None


# saves database record for a war battle; if player_id is None, does nothing
# if a record with the same timestamp exists for a user, does nothing (assume two different battles
# cannot happen at the same time for the same player)
def save_battle(player_id, datetime_string, decks_used, decks_won, fame):
    # if player_id is None:
    #    return
    dt = _parse_cr_date(datetime_string)
    war_day = _get_war_day(dt)
    # print("""
    #       INSERT INTO war_battle (player_id, timestamp, war_day, decks_used, decks_won, fame)\n
    #       VALUES (%d, '%s', '%s', %d, %d, %d);
    #       """ % (1, dt, war_day, decks_used, decks_won, fame))
