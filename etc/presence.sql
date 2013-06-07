PRAGMA foreign_keys = ON;

CREATE TABLE people (
  id integer PRIMARY KEY AUTOINCREMENT,
  name varchar unique,
  nick varchar unique,
  irc_nick varchar unique,
  last_sighting datetime,
  last_announce datetime
);

CREATE TABLE macs (
  person_id integer REFERENCES people (id),
  mac varchar(17) UNIQUE NOT NULL,
  hostname varchar,
  description varchar,
  ip varchar,
  first_sighting datetime DEFAULT CURRENT_TIMESTAMP,
  last_sighting datetime
);

CREATE TABLE cards (
  person_id integer REFERENCES people (id),
  uid varchar UNIQUE NOT NULL,
  description varchar,
  first_sighting datetime DEFAULT CURRENT_TIMESTAMP,
  last_sighting datetime
);
