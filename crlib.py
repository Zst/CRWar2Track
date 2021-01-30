# Common utils for accessing Clash Royale API
import requests
import sys

clan_tag = "YJCGRV9"  # Heavyweights


def load_auth():
    try:
        with open("auth.txt", "r") as f:
            rv = "Bearer " + f.read().rstrip()
            return rv
    except IOError:
        sys.exit("Could not read authentication token, make sure one is available in an auth.txt file.")


auth = load_auth()


def get_clan_name(clan_tag):
    r = requests.get("https://api.clashroyale.com/v1/clans/%23" + clan_tag,
                     headers={"Accept": "application/json", "authorization": auth},
                     params={"limit": 50, "clanTag": clan_tag})
    return r.json()["name"]


def get_player_name(player_tag):
    r = requests.get("https://api.clashroyale.com/v1/players/%23" + player_tag,
                     headers={"Accept": "application/json", "authorization": auth},
                     params={"limit": 50, "playerTag": player_tag})
    return r.json()["name"]


def clan_member_tags(ct):
    tags = []
    r = requests.get("https://api.clashroyale.com/v1/clans/%23" + ct + "/members",
                     headers={"Accept": "application/json", "authorization": auth},
                     params={"limit": 50})

    members = r.json()["items"]
    for m in members:
        tags.append(m["tag"][1:])
    return tags
