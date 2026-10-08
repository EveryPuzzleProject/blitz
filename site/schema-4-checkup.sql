-- The grade of each puzzle's review (check closely / worth a look / looks clean), so the puzzle list can show it and
-- filter on it. Run once in the Supabase SQL editor. Until it has been run the site just doesn't show grades;
-- `blitz site-publish` then puts the grades in as it publishes.

alter table puzzles add column if not exists checkup jsonb;  -- {"grade": "check" | "look" | "clean", "high": n, "medium": n}
