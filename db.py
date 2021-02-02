import datetime

import psycopg2
from decouple import config

from utils import log, err

QUERY_MARK_LEAVERS = "UPDATE player SET is_in_clan = id IN (%s);"
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

QUERY_CLEAR_NOTIFICATION_IDS = 'UPDATE player SET discord_id = NULL;'

QUERY_UPDATE_PLAYER_NOTIFICATION_ID = """
    UPDATE player
    SET discord_id = '%s', is_mini = %s
    WHERE tag = '%s';
"""

QUERY_GET_WAR_DAY_STATS = """
    SELECT count(players) as players, sum(played) as played, sum(won) as won 
    FROM (
        SELECT count(*) as players, sum(decks_used) as played, sum(decks_won) as won
        FROM war_battle
        WHERE war_day = '%s'
        GROUP BY player_id
    ) as p
"""

QUERY_GET_WAR_DAY_PLAYER_STATS = """
    SELECT p.name, p.discord_id, p.is_in_clan, p.is_mini, SUM(COALESCE(wb.decks_used, 0)) as used
    FROM player p
    LEFT JOIN war_battle wb ON wb.player_id = p.id AND wb.war_day = '%s'
    WHERE p.is_in_clan OR wb.decks_used is NOT NULL
    GROUP BY p.id
    HAVING SUM(COALESCE(wb.decks_used, 0)) < 4
    ORDER BY 5;
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


def _execute_query(query_str, ignore_duplication_errors=False):
    if conn is None:
        return
    cur = conn.cursor()
    try:
        cur.execute(query_str)
        cur.close()
        conn.commit()
    except Exception as e:
        conn.rollback()
        if not ignore_duplication_errors or 'duplicate' not in str(e):
            err('Cannot execute database query: ' + str(e))


def _fetch_query(query_str):
    if conn is None:
        return None
    cur = conn.cursor()
    res = None
    try:
        cur.execute(query_str)
        res = cur.fetchall()
    except Exception as e:
        err('Cannot get run select query: ' + str(e))
        return res
    finally:
        cur.close()
    return res


# marks players not listed in the `players_in_clan` list as the ones not currently in clan
def mark_leavers(players_in_clan):
    _execute_query(QUERY_MARK_LEAVERS % ','.join(str(p) for p in players_in_clan))


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
def save_battle(player_id, timestamp, war_day, decks_used, decks_won, fame):
    _execute_query(QUERY_INSERT_BATTLE % (player_id, timestamp, war_day, decks_used, decks_won, fame), True)


def reset_notification_ids():
    _execute_query(QUERY_CLEAR_NOTIFICATION_IDS)


def set_player_notification_id(player_tag, notification_id, is_mini):
    _execute_query(QUERY_UPDATE_PLAYER_NOTIFICATION_ID % (notification_id.replace("'", "\\'"),
                                                          is_mini,
                                                          player_tag.replace("'", "\\'")))


def get_war_day_stats(war_day):
    return _fetch_query(QUERY_GET_WAR_DAY_STATS % war_day)


def get_war_day_player_stats(war_day):
    return _fetch_query(QUERY_GET_WAR_DAY_PLAYER_STATS % war_day)


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
                set_item(row_idx, col * 2 + 1, row[1])
                set_item(row_idx, col * 2 + 2, row[2])
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
                day_battles_played += res[p][1 + d * 2] or 0
                day_battles_won += res[p][1 + d * 2 + 1] or 0
                if day_battles_played:
                    day_players += 1
            except IndexError:
                pass

        if day_battles_played > 0:
            # maximum number of battles per clan per day is 50 * 4 = 200, print % of those that are actually played
            set_item(2, 1 + d * 2, str(round(100 * day_battles_played / 200, 2)) + '% (' + str(day_players) + ')')
            set_item(2, 1 + d * 2 + 1, str(round(100 * day_battles_won / day_battles_played, 2)) + '%')

    return res
