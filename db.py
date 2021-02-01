import datetime

import psycopg2
from decouple import config

from utils import log, err

QUERY_MARK_LEAVERS = "UPDATE player SET is_in_clan = false WHERE id NOT IN (%s)"
QUERY_INSERT_PLAYER = """
    INSERT INTO player (tag, name) VALUES ('%s', '%s')
    ON CONFLICT (tag) 
    DO 
    UPDATE SET name = EXCLUDED.name;
    SELECT id FROM player WHERE tag = '%s';
"""
QUERY_INSERT_BATTLE = """
    INSERT INTO war_battle (player_id, battle_timestamp, war_day, decks_used, decks_won, fame)\n
    VALUES (%d, '%s', '%s', %d, %d, %d);
"""

QUERY_GET_LAST_WEEK_STATS = """
    SELECT wb.war_day, SUM(wb.decks_used) as played, SUM(wb.decks_won) as won, p.id as player_id, p.name,
        p.is_in_clan
    FROM player p
    LEFT JOIN war_battle wb ON wb.player_id = p.id AND wb.war_day >= '%s'
    WHERE p.is_in_clan OR wb.id != NULL
    GROUP BY p.id, wb.war_day
    ORDER BY p.is_in_clan DESC, p.id, wb.war_day
"""


def get_connection():
    try:
        return psycopg2.connect(
            database=config('DB_DATABASE'),
            user=config('DB_USER'),
            password=config('DB_PASSWORD'),
            host='127.0.0.1',
            port=config('DB_PORT')
        )
    except Exception as e:
        log('Database connection failed, the data will not be saved: ' + str(e))
        return None


conn = get_connection()


# determines war day date from the battle timestamp
def _get_war_day(dt):
    if dt.time() < datetime.time(10):
        return (dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        return dt.strftime("%Y-%m-%d")


# parses datetime format of the CR API
def _parse_cr_date(datetime_string):
    return datetime.datetime.strptime(datetime_string, '%Y%m%dT%H%M%S.%fZ')


# marks players not listed in the `players_in_clan` list as the ones not currently in clan
def mark_leavers(players_in_clan):
    if conn is None:
        return
    cur = conn.cursor()
    try:
        cur.execute(QUERY_MARK_LEAVERS % ','.join(str(p) for p in players_in_clan))
        cur.close()
        conn.commit()
    except Exception as e:
        conn.rollback()
        err('Cannot mark users out of the clan: ' + str(e))


# returns player id from the database; if record doesn't exist, creates it
def get_player_id(player_tag, player_name):
    if conn is None:
        return None
    cur = conn.cursor()
    try:
        cur.execute(QUERY_INSERT_PLAYER % (player_tag, player_name.replace("'", "\\'"), player_tag))
        res = cur.fetchone()
        player_id = res[0]
        cur.close()
        conn.commit()
        return player_id
    except Exception as e:
        conn.rollback()
        err('Cannot get or create user: ' + str(e))
        return None


# saves database record for a war battle; if player_id is None, does nothing
# if a record with the same timestamp exists for a user, does nothing (assume two different battles
# cannot happen at the same time for the same player)
def save_battle(player_id, datetime_string, decks_used, decks_won, fame):
    if conn is None or player_id is None:
        return
    dt = _parse_cr_date(datetime_string)
    war_day = _get_war_day(dt)
    cur = conn.cursor()
    try:
        cur.execute(QUERY_INSERT_BATTLE % (player_id, dt, war_day, decks_used, decks_won, fame))
        cur.close()
        # a little wasteful to commit after each insert, will make it more efficient later
        conn.commit()
    except Exception as e:
        conn.rollback()
        # we expect duplication errors, will print out everything else
        if 'duplicate' not in str(e):
            err('Cannot insert war battle: ' + str(e))


# returns two-dimensional array for export. Format:
# [[Report date][<datetime>]]
# [[Player][Played <date (Sun)>][Won <date (Sun)>]...[Played <date (today)>][Won <date (today)>]]
def get_report(cutout_date):
    def set_item(i, j, v):
        try:
            res[i][j] = v
        except IndexError:
            for _ in range(i - len(res) + 1):
                res.append([])
            for _ in range(j - len(res[i]) + 1):
                res[i].append(None)
            res[i][j] = v

    def get_day_index(war_day):
        return (war_day - cutout_datetime.date()).days

    if conn is None:
        return None
    res = []
    cutout_datetime = datetime.datetime.strptime(cutout_date, '%Y-%m-%d')

    today = datetime.datetime.utcnow()
    days_in_report = get_day_index(today.date()) + 1

    set_item(0, 0, 'Last update: ' + today.strftime('%d-%m-%Y %H:%M:%S'))
    # filling in table header
    for d in range(days_in_report):
        set_item(0, 1 + d * 2, (cutout_datetime + datetime.timedelta(days=d)).date().strftime('%d-%m-%Y'))
        set_item(1, 1 + d * 2, 'played')
        set_item(1, 1 + d * 2 + 1, 'won')

    # iterating through query result, each row is a player's war day
    # row_idx = 2 will make it start from row 3 (we increment in the beginning), first 3 rows are reserved
    # for headers and totals
    row_idx = 2
    last_player_id = None
    cur = conn.cursor()
    try:
        cur.execute(QUERY_GET_LAST_WEEK_STATS % cutout_date)
        for row in cur:
            if row[3] != last_player_id:
                row_idx += 1
                last_player_id = row[3]
                set_item(row_idx, 0, row[4] + (' (not in clan)' if not row[5] else ''))
            if row[0] is not None:
                col = get_day_index(row[0])
                set_item(row_idx, col*2 + 1, row[1])
                set_item(row_idx, col*2 + 2, row[2])
    finally:
        cur.close()

    # counting totals and averages
    set_item(2, 0, 'TOTAL')
    for d in range(days_in_report):
        day_battles_played = 0
        day_battles_won = 0
        day_players = 0
        for p in range(2, len(res)):
            try:
                day_battles_played += res[p][1 + d*2] or 0
                day_battles_won += res[p][1 + d*2 + 1] or 0
                if day_battles_played:
                    day_players += 1
            except IndexError:
                pass

        if day_battles_played > 0:
            # maximum number of battles per clan per day is 50 * 4 = 200, print % of those that are actually played
            set_item(2, 1 + d * 2, str(round(100 * day_battles_played / 200, 2)) + '% (' + str(day_players) + ')')
            set_item(2, 1 + d * 2 + 1, str(round(100 * day_battles_won / day_battles_played, 2)) + '%')

    return res
