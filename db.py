import datetime

import sys
import psycopg2
from decouple import config

query_mark_leavers = "UPDATE player SET is_in_clan = false WHERE id NOT IN (%s)"
query_insert_player = """
    INSERT INTO player (tag, name) VALUES ('%s', '%s')
    ON CONFLICT (tag) 
    DO 
    UPDATE SET name = EXCLUDED.name;
    SELECT id FROM player WHERE tag = '%s';
"""
query_get_player = ""
query_insert_battle = """
    INSERT INTO war_battle (player_id, battle_timestamp, war_day, decks_used, decks_won, fame)\n
    VALUES (%d, '%s', '%s', %d, %d, %d);
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
    except:
        print("Database connection failed, the data will not be saved")
        return None


conn = get_connection()


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
    if conn is None:
        return
    cur = conn.cursor()
    try:
        cur.execute(query_mark_leavers % ','.join(str(p) for p in players_in_clan))
        cur.close()
        conn.commit()
    except Exception as e:
        conn.rollback()
        sys.stderr.write('Cannot mark users out of the clan: ' + str(e))


# returns player id from the database; if record doesn't exist, creates it
def get_player_id(player_tag, player_name):
    if conn is None:
        return None
    cur = conn.cursor()
    try:
        cur.execute(query_insert_player % (player_tag, player_name.replace("'", "\\'"), player_tag))
        res = cur.fetchone()
        player_id = res[0]
        cur.close()
        conn.commit()
        return player_id
    except Exception as e:
        conn.rollback()
        sys.stderr.write('Cannot get or create user: ' + str(e))
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
        cur.execute(query_insert_battle % (player_id, dt, war_day, decks_used, decks_won, fame))
        cur.close()
        # a little wasteful to commit after each insert, will make it more efficient later
        conn.commit()
    except Exception as e:
        conn.rollback()
        # we expect duplication errors, will print out everything else
        if 'duplicate' not in str(e):
            sys.stderr.write('Cannot insert war battle: ' + str(e))
