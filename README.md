# CRWar2Track
Scripts to track Clas Royale's war 2 clan participation

The purpose of these scripts are to help manage an active war clan in Clash Royale.
It shows participation during the last 24 hours, which we use to chase people to complete
their war day battles. Alternatively, it can save war participation stats in a database and export last week report to a Google spreadsheet document.

## Setup
### Basic features
To get current day report:
* Register on developer.clashroyale.com/
* Create an `auth.txt` file with the authorization token inside.
* Create `.env` file and save main clan id (without `#` char, see `.env.example`
* Create venv (optionally) and install dependencies
* Run script: `python CW2DayAnalysis.py`

### Save to database
To save player data in a database:
* Install PostgreSQL
* Create database
* Manually run migrations from `migrations` folder
* Add database access parameters to `.env` (see `.env.example`)

### Export to Google Sheets
To let script export last week report to Google Sheets:
* Create service account - follow the guide [on Medium](https://denisluiz.medium.com/python-with-google-sheets-service-account-step-by-step-8f74c26ed28e)
  * Enable Google Drive API
  * Create service account credentials
  * Create key with json format
  * Download json key and place it in the project with `client_secret.json` name
* Create target spreadsheet and give write access to it to the user with email specified in `client_secret.json`
* Set spreadsheet id (hash in URL) in `.env`


## Manual mode
If database connection is not set up or the script is launched in manual mode with overriding clan tag in command line arguments (`python CW2DayAnalysis.py <clan tag>`), it will output the current date stats to stdout following next rules:

Determine the start of the war day. On Mondays it is the last 9:30am GMT,
on other days it is the last 10:00am GMT. The script will go through all the current clan 
members, and list the number of war day battles they played. E.g.
```
player1: 4
player2: 4
player3: 3
playern: 0
```

Note that only the last 25 games are available per player, so war day information may not be
available. The script will give a warning in such cases for the player:

```
playerFoo: 2 25+ games since war start
```

## Database structure features and considerations
`player` table has `is_in_clan` field which denotes players present in clan during last script run. It does not affect any calculations but help to arrange data in report.

We rely on `UNIQUE (player_id, battle_timestamp)` database constraint to prevent data duplication, otherwise all war battles are saved. Boat battles are always counted as a loss.

`war_day` field in `war_battle` is always set to `battle day - 1` if battle timestamp is before 10:00am GMT. That means that neither report nor database structure is accounting for the 'glitch' battles that happen between war week start and decks reset. Those battles will be counted towards Sunday war day and can be further researched based on saved `battle_timestamp` value.

`fame` and `discord_id` fields are not used and reserved for future features.

## Reports

Every script run all data in the target spreadsheet is removed and then inserted again. Styling is preserved during these operations. Therefore, we try to put summary and general information in the first rows/columns because of variable total number of rows and columns in reports.

Total numbers per day should be read as following:
* `played` - current percentage of 200 maximum possible battles per day (50 player, 4 battles each)
* `won` - win percentage in actually played battles
