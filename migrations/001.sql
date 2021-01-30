CREATE TABLE player (
	id SERIAL PRIMARY KEY,
	tag VARCHAR ( 12 ) UNIQUE NOT NULL,
	name VARCHAR ( 50 ) NOT NULL,
	discord_id VARCHAR ( 50 ) NULL,
	is_in_clan BOOL NOT NULL DEFAULT True
);

CREATE TABLE war_battle (
	id SERIAL PRIMARY KEY,
	player_id INT NOT NULL,
	battle_timestamp TIMESTAMP NOT NULL,
	war_day DATE NOT NULL,
	decks_used INT NOT NULL DEFAULT 1,
	decks_won INT NOT NULL DEFAULT 1,
	fame INT,
	
	UNIQUE (player_id, battle_timestamp),
	FOREIGN KEY (player_id)
      REFERENCES player (id)
);