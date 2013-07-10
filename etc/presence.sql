PRAGMA foreign_keys = ON;

CREATE TABLE people (
  id integer PRIMARY KEY AUTOINCREMENT,
  name varchar unique,
  nick varchar unique,
  irc_nick varchar unique,
  last_sighting datetime,
  last_announce datetime,
  announce_public boolean default 0,
  announce_private boolean default 1
);

CREATE TABLE macs (
  person_id integer REFERENCES people (id),
  mac varchar(17) UNIQUE NOT NULL,
  hostname varchar,
  description varchar,
  ip varchar,
  first_sighting datetime DEFAULT CURRENT_TIMESTAMP,
  last_sighting datetime,
  static boolean NOT NULL DEFAULT 0
);

CREATE TABLE cards (
  person_id integer REFERENCES people (id),
  uid varchar UNIQUE NOT NULL,
  description varchar,
  first_sighting datetime DEFAULT CURRENT_TIMESTAMP,
  last_sighting datetime
);
