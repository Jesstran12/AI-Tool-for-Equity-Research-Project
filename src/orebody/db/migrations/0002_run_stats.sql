-- F6.4 run stats (SPEC §5.5): verification counts per run, stored as JSON so later tiers
-- (F6.2 tier 2) can add fields without another migration.
ALTER TABLE runs ADD COLUMN stats TEXT NOT NULL DEFAULT '{}';
