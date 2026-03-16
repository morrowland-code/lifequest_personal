from __future__ import annotations

import os
from contextlib import closing
from datetime import date, datetime, timezone

import psycopg
from psycopg.rows import dict_row
from flask import Flask, flash, g, redirect, render_template, request, url_for


DATABASE_URL = os.environ.get("DATABASE_URL")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

TRAIT_PROFILE = {
    "archetype": "Terrabeacon",
    "openness": "High",
    "conscientiousness": "Low",
    "extraversion": "Low",
    "agreeableness": "Low",
    "neuroticism": "High",
}

ENERGY_PRESETS = {
    "low": {"main": 1, "side": 0, "stability": 1, "reflection": 1, "tiny": 1},
    "normal": {"main": 1, "side": 1, "stability": 1, "reflection": 1, "tiny": 1},
    "hyperfocus": {"main": 1, "side": 2, "stability": 1, "reflection": 0, "tiny": 1},
    "overwhelmed": {"main": 0, "side": 0, "stability": 1, "reflection": 1, "tiny": 1},
}

CAMPAIGN_OPTIONS = [
    "The Knowledge Forge",
    "The Symbolic Craft",
    "The Digital Architect",
    "The Signal Amplifier",
    "The Grounding Cycle",
]

CATEGORY_OPTIONS = ["main", "side", "stability", "reflection", "tiny"]

STARTER_OUTFITS = [
    {"name": "Pink Starter Fit", "slot": "outfit", "rarity": "common", "unlock_level": 1, "xp_cost": 0},
    {"name": "Study Bunny Hoodie", "slot": "outfit", "rarity": "common", "unlock_level": 2, "xp_cost": 150},
    {"name": "Cosmic Coder Jacket", "slot": "outfit", "rarity": "rare", "unlock_level": 4, "xp_cost": 400},
    {"name": "Dream Mage Dress", "slot": "outfit", "rarity": "epic", "unlock_level": 6, "xp_cost": 800},
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db():
    if "db" not in g:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not set.")
        g.db = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def safe_int(value, default=0, minimum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default

    if minimum is not None:
        parsed = max(minimum, parsed)
    return parsed


def init_db():
    schema = """
    CREATE TABLE IF NOT EXISTS profile_settings (
        id INTEGER PRIMARY KEY,
        energy_mode TEXT NOT NULL DEFAULT 'normal',
        total_xp INTEGER NOT NULL DEFAULT 0,
        level INTEGER NOT NULL DEFAULT 1,
        current_xp INTEGER NOT NULL DEFAULT 0,
        daily_streak INTEGER NOT NULL DEFAULT 0,
        last_activity_date TEXT
    );

    CREATE TABLE IF NOT EXISTS campaigns (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS quests (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        notes TEXT DEFAULT '',
        campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL,
        category TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'todo',
        xp_reward INTEGER NOT NULL DEFAULT 25,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        is_today INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS strategies (
        id SERIAL PRIMARY KEY,
        quest_id INTEGER NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
        text TEXT NOT NULL,
        completed INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS idea_vault (
        id SERIAL PRIMARY KEY,
        text TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS daily_log (
        id INTEGER PRIMARY KEY,
        protein_goal INTEGER NOT NULL DEFAULT 120,
        protein_value INTEGER NOT NULL DEFAULT 0,
        water_goal INTEGER NOT NULL DEFAULT 8,
        water_value INTEGER NOT NULL DEFAULT 0,
        workout_done INTEGER NOT NULL DEFAULT 0,
        reflection_text TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS character_profile (
        id INTEGER PRIMARY KEY,
        character_name TEXT NOT NULL DEFAULT 'Terrabeacon Hero',
        current_outfit_id INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS outfit_store (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        slot TEXT NOT NULL DEFAULT 'outfit',
        rarity TEXT NOT NULL DEFAULT 'common',
        unlock_level INTEGER NOT NULL DEFAULT 1,
        xp_cost INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS owned_outfits (
        id SERIAL PRIMARY KEY,
        outfit_id INTEGER NOT NULL UNIQUE REFERENCES outfit_store(id) ON DELETE CASCADE,
        unlocked_at TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'level'
    );
    """

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set.")

    with closing(psycopg.connect(DATABASE_URL, row_factory=dict_row)) as db:
        with db.cursor() as cur:
            cur.execute(schema)

            cur.execute("""
                INSERT INTO profile_settings (id, energy_mode, total_xp, level, current_xp, daily_streak, last_activity_date)
                VALUES (1, 'normal', 0, 1, 0, 0, NULL)
                ON CONFLICT (id) DO NOTHING
            """)

            cur.execute("INSERT INTO daily_log (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
            cur.execute("INSERT INTO character_profile (id) VALUES (1) ON CONFLICT (id) DO NOTHING")

            for name in CAMPAIGN_OPTIONS:
                cur.execute(
                    "INSERT INTO campaigns (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                    (name,),
                )

            for outfit in STARTER_OUTFITS:
                cur.execute(
                    """
                    INSERT INTO outfit_store (name, slot, rarity, unlock_level, xp_cost)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (name) DO NOTHING
                    """,
                    (
                        outfit["name"],
                        outfit["slot"],
                        outfit["rarity"],
                        outfit["unlock_level"],
                        outfit["xp_cost"],
                    ),
                )

        db.commit()

    with app.app_context():
        unlock_outfits_for_level()


def unlock_outfits_for_level():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT level FROM profile_settings WHERE id = 1")
        profile = cur.fetchone()
        level = profile["level"]

        cur.execute(
            """
            SELECT id, name
            FROM outfit_store
            WHERE unlock_level <= %s
              AND id NOT IN (SELECT outfit_id FROM owned_outfits)
            ORDER BY unlock_level, id
            """,
            (level,),
        )
        eligible = cur.fetchall()

        unlocked_names = []
        for row in eligible:
            cur.execute(
                """
                INSERT INTO owned_outfits (outfit_id, unlocked_at, source)
                VALUES (%s, %s, 'level')
                ON CONFLICT (outfit_id) DO NOTHING
                """,
                (row["id"], utc_now_iso()),
            )
            unlocked_names.append(row["name"])

        cur.execute("SELECT current_outfit_id FROM character_profile WHERE id = 1")
        current = cur.fetchone()

        if current["current_outfit_id"] is None:
            cur.execute(
                """
                SELECT outfit_id
                FROM owned_outfits
                ORDER BY id ASC
                LIMIT 1
                """
            )
            first_owned = cur.fetchone()

            if first_owned:
                cur.execute(
                    "UPDATE character_profile SET current_outfit_id = %s WHERE id = 1",
                    (first_owned["outfit_id"],),
                )

    db.commit()
    return unlocked_names


def get_character_data():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM character_profile WHERE id = 1")
        character = cur.fetchone()

        current_outfit = None
        if character and character["current_outfit_id"]:
            cur.execute(
                "SELECT * FROM outfit_store WHERE id = %s",
                (character["current_outfit_id"],),
            )
            current_outfit = cur.fetchone()

        cur.execute(
            """
            SELECT os.*, oo.unlocked_at, oo.source
            FROM outfit_store os
            JOIN owned_outfits oo ON oo.outfit_id = os.id
            ORDER BY os.unlock_level, os.id
            """
        )
        owned_outfits = cur.fetchall()

    return character, current_outfit, owned_outfits


def add_xp(amount):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT level, current_xp FROM profile_settings WHERE id = 1"
        )
        profile = cur.fetchone()

        old_level = profile["level"]
        level = old_level
        xp = profile["current_xp"] + amount
        leveled_up = False

        while xp >= level * 100:
            xp -= level * 100
            level += 1
            leveled_up = True

        cur.execute(
            """
            UPDATE profile_settings
            SET level = %s, current_xp = %s, total_xp = total_xp + %s
            WHERE id = 1
            """,
            (level, xp, amount),
        )

    db.commit()

    unlocked_outfits = []
    if level > old_level:
        unlocked_outfits = unlock_outfits_for_level()

    return leveled_up, level, unlocked_outfits


def apply_daily_streak():
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT daily_streak, last_activity_date FROM profile_settings WHERE id = 1"
        )
        profile = cur.fetchone()

        today = date.today()
        today_str = today.isoformat()
        last_date_str = profile["last_activity_date"]
        current_streak = profile["daily_streak"] or 0

        if last_date_str == today_str:
            return 0, current_streak, False

        streak_bonus = 0
        new_streak = 1

        if last_date_str:
            try:
                last_date = date.fromisoformat(last_date_str)
                delta_days = (today - last_date).days
                if delta_days == 1:
                    new_streak = current_streak + 1
            except ValueError:
                new_streak = 1

        if new_streak > 1:
            streak_bonus = min(new_streak * 5, 50)

        cur.execute(
            """
            UPDATE profile_settings
            SET daily_streak = %s, last_activity_date = %s
            WHERE id = 1
            """,
            (new_streak, today_str),
        )

    db.commit()
    return streak_bonus, new_streak, True


def get_campaign_progress():
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
                c.id,
                c.name,
                COUNT(q.id) AS total_quests,
                COALESCE(SUM(CASE WHEN q.status = 'done' THEN 1 ELSE 0 END), 0) AS completed_quests
            FROM campaigns c
            LEFT JOIN quests q ON q.campaign_id = c.id
            GROUP BY c.id, c.name
            ORDER BY c.name
            """
        )
        rows = cur.fetchall()

    progress = []
    for row in rows:
        total = row["total_quests"] or 0
        completed = row["completed_quests"] or 0
        percent = round((completed / total) * 100, 1) if total > 0 else 0
        progress.append(
            {
                "id": row["id"],
                "name": row["name"],
                "total_quests": total,
                "completed_quests": completed,
                "percent": percent,
            }
        )
    return progress


@app.route("/")
def dashboard():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM profile_settings WHERE id = 1")
        settings = cur.fetchone()

        cur.execute("SELECT * FROM daily_log WHERE id = 1")
        daily_log = cur.fetchone()

        energy_mode = settings["energy_mode"]
        limits = ENERGY_PRESETS.get(energy_mode, ENERGY_PRESETS["normal"])

        quest_board = {}
        for category in CATEGORY_OPTIONS:
            limit = limits.get(category, 0)
            cur.execute(
                """
                SELECT q.*, c.name AS campaign_name,
                       (SELECT COUNT(*) FROM strategies s WHERE s.quest_id = q.id) AS strategy_count
                FROM quests q
                LEFT JOIN campaigns c ON c.id = q.campaign_id
                WHERE q.status = 'todo' AND q.category = %s
                ORDER BY q.id ASC
                LIMIT %s
                """,
                (category, limit),
            )
            quest_board[category] = cur.fetchall()

        cur.execute(
            """
            SELECT q.*, c.name AS campaign_name,
                   (SELECT COUNT(*) FROM strategies s WHERE s.quest_id = q.id) AS strategy_count
            FROM quests q
            LEFT JOIN campaigns c ON c.id = q.campaign_id
            WHERE q.status = 'todo'
            ORDER BY q.id DESC
            """
        )
        active_quests = cur.fetchall()

        cur.execute(
            """
            SELECT q.*, c.name AS campaign_name,
                   (SELECT COUNT(*) FROM strategies s WHERE s.quest_id = q.id) AS strategy_count
            FROM quests q
            LEFT JOIN campaigns c ON c.id = q.campaign_id
            WHERE q.status = 'todo' AND q.is_today = 1
            ORDER BY q.id ASC
            """
        )
        today_quests = cur.fetchall()

        cur.execute(
            """
            SELECT q.*, c.name AS campaign_name
            FROM quests q
            LEFT JOIN campaigns c ON c.id = q.campaign_id
            WHERE q.status = 'done'
            ORDER BY q.completed_at DESC
            LIMIT 20
            """
        )
        completed_quests = cur.fetchall()

        cur.execute(
            """
            SELECT s.*, q.title AS quest_title
            FROM strategies s
            JOIN quests q ON q.id = s.quest_id
            WHERE q.status = 'todo'
            ORDER BY q.id ASC, s.id ASC
            """
        )
        strategies = cur.fetchall()

        cur.execute("SELECT * FROM campaigns ORDER BY name")
        campaigns = cur.fetchall()

        cur.execute("SELECT * FROM idea_vault ORDER BY id DESC LIMIT 8")
        ideas = cur.fetchall()

    campaign_progress = get_campaign_progress()
    character, current_outfit, owned_outfits = get_character_data()

    return render_template(
        "dashboard.html",
        profile=TRAIT_PROFILE,
        settings=settings,
        daily_log=daily_log,
        quest_board=quest_board,
        active_quests=active_quests,
        today_quests=today_quests,
        completed_quests=completed_quests,
        campaigns=campaigns,
        ideas=ideas,
        energy_presets=ENERGY_PRESETS,
        campaign_progress=campaign_progress,
        character=character,
        current_outfit=current_outfit,
        owned_outfits=owned_outfits,
        strategies=strategies,
    )


@app.post("/energy")
def set_energy():
    energy_mode = request.form.get("energy_mode", "normal")
    if energy_mode not in ENERGY_PRESETS:
        energy_mode = "normal"

    db = get_db()
    with db.cursor() as cur:
        cur.execute("UPDATE profile_settings SET energy_mode = %s WHERE id = 1", (energy_mode,))
    db.commit()

    flash(f"Energy mode set to {energy_mode}.")
    return redirect(url_for("dashboard"))


@app.post("/quests/<int:quest_id>/add-to-today")
def add_quest_to_today(quest_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM quests WHERE id = %s", (quest_id,))
        quest = cur.fetchone()

        if not quest:
            flash("Quest not found.")
            return redirect(url_for("dashboard"))

        if quest["status"] == "done":
            flash("Completed quests cannot be added to Today Focus.")
            return redirect(url_for("dashboard"))

        cur.execute("UPDATE quests SET is_today = 1 WHERE id = %s", (quest_id,))
    db.commit()

    flash(f"Added to Today Focus: {quest['title']}.")
    return redirect(url_for("dashboard"))


@app.post("/quests/<int:quest_id>/remove-from-today")
def remove_quest_from_today(quest_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM quests WHERE id = %s", (quest_id,))
        quest = cur.fetchone()

        if not quest:
            flash("Quest not found.")
            return redirect(url_for("dashboard"))

        cur.execute("UPDATE quests SET is_today = 0 WHERE id = %s", (quest_id,))
    db.commit()

    flash(f"Removed from Today Focus: {quest['title']}.")
    return redirect(url_for("dashboard"))


@app.post("/character/equip/<int:outfit_id>")
def equip_outfit(outfit_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT os.*
            FROM outfit_store os
            JOIN owned_outfits oo ON oo.outfit_id = os.id
            WHERE os.id = %s
            """,
            (outfit_id,),
        )
        owned = cur.fetchone()

        if not owned:
            flash("You don't own that outfit yet.")
            return redirect(url_for("dashboard"))

        cur.execute(
            "UPDATE character_profile SET current_outfit_id = %s WHERE id = 1",
            (outfit_id,),
        )
    db.commit()

    flash(f"Equipped outfit: {owned['name']}.")
    return redirect(url_for("dashboard"))


@app.post("/quests")
def add_quest():
    title = request.form.get("title", "").strip()
    notes = request.form.get("notes", "").strip()
    category = request.form.get("category", "side")
    campaign_id = request.form.get("campaign_id") or None
    xp_reward = safe_int(request.form.get("xp_reward", 25), default=25, minimum=0)
    strategies_raw = request.form.get("strategies", "").strip()

    if not title:
        flash("Quest title is required.")
        return redirect(url_for("dashboard"))

    if category not in CATEGORY_OPTIONS:
        category = "side"

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO quests (title, notes, campaign_id, category, status, xp_reward, created_at, is_today)
            VALUES (%s, %s, %s, %s, 'todo', %s, %s, 0)
            RETURNING id
            """,
            (title, notes, campaign_id, category, xp_reward, utc_now_iso()),
        )
        quest_id = cur.fetchone()["id"]

        strategy_lines = [s.strip() for s in strategies_raw.splitlines() if s.strip()]
        for line in strategy_lines:
            cur.execute(
                "INSERT INTO strategies (quest_id, text, completed) VALUES (%s, %s, 0)",
                (quest_id, line),
            )

    db.commit()

    strategy_xp = len(strategy_lines) * 10
    leveled, level, unlocked_outfits = add_xp(strategy_xp)

    message = f"Quest added. Strategy XP earned: {strategy_xp}."
    if leveled:
        message += f" You leveled up to Level {level}!"
    if unlocked_outfits:
        message += " New outfit unlocked: " + ", ".join(unlocked_outfits) + "."

    flash(message)
    return redirect(url_for("dashboard"))


@app.post("/quests/<int:quest_id>/complete")
def complete_quest(quest_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM quests WHERE id = %s", (quest_id,))
        quest = cur.fetchone()

        if not quest:
            flash("Quest not found.")
            return redirect(url_for("dashboard"))

        if quest["status"] == "done":
            flash("Quest already completed.")
            return redirect(url_for("dashboard"))

        total_gain = quest["xp_reward"]
        cur.execute(
            "UPDATE quests SET status = 'done', completed_at = %s, is_today = 0 WHERE id = %s",
            (utc_now_iso(), quest_id),
        )
    db.commit()

    streak_bonus, new_streak, streak_updated = apply_daily_streak()
    base_leveled, base_level, base_outfits = add_xp(total_gain)

    leveled = base_leveled
    level = base_level
    unlocked_outfits = list(base_outfits)

    if streak_bonus > 0:
        streak_leveled, streak_level, streak_outfits = add_xp(streak_bonus)
        unlocked_outfits.extend(streak_outfits)
        if streak_leveled:
            leveled = True
            level = streak_level

    if unlocked_outfits:
        unlocked_outfits = list(dict.fromkeys(unlocked_outfits))

    message = f"Quest completed. XP earned: {total_gain}."
    if streak_updated:
        message += f" Streak: {new_streak} day"
        if new_streak != 1:
            message += "s"
        message += "."
    if streak_bonus > 0:
        message += f" Streak bonus XP: {streak_bonus}."
    if leveled:
        message += f" You leveled up to Level {level}!"
    if unlocked_outfits:
        message += " New outfit unlocked: " + ", ".join(unlocked_outfits) + "."

    flash(message)
    return redirect(url_for("dashboard"))


@app.post("/quests/<int:quest_id>/delete")
def delete_quest(quest_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM quests WHERE id = %s", (quest_id,))
        quest = cur.fetchone()

        if not quest:
            flash("Quest not found.")
            return redirect(url_for("dashboard"))

        cur.execute("DELETE FROM quests WHERE id = %s", (quest_id,))
    db.commit()

    flash(f"Deleted quest: {quest['title']}.")
    return redirect(url_for("dashboard"))


@app.post("/strategies/<int:strategy_id>/complete")
def complete_strategy(strategy_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT s.*, q.title AS quest_title
            FROM strategies s
            JOIN quests q ON q.id = s.quest_id
            WHERE s.id = %s
            """,
            (strategy_id,),
        )
        strategy = cur.fetchone()

        if not strategy:
            flash("Strategy not found.")
            return redirect(url_for("dashboard"))

        if strategy["completed"]:
            flash("Strategy already completed.")
            return redirect(url_for("dashboard"))

        cur.execute(
            "UPDATE strategies SET completed = 1 WHERE id = %s",
            (strategy_id,),
        )
    db.commit()

    leveled, level, unlocked_outfits = add_xp(10)

    message = f"Strategy completed for {strategy['quest_title']}! +10 XP."
    if leveled:
        message += f" You leveled up to Level {level}!"
    if unlocked_outfits:
        message += " New outfit unlocked: " + ", ".join(unlocked_outfits) + "."

    flash(message)
    return redirect(url_for("dashboard"))


@app.post("/ideas")
def add_idea():
    text = request.form.get("text", "").strip()
    if not text:
        flash("Idea text is required.")
        return redirect(url_for("dashboard"))

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO idea_vault (text, created_at) VALUES (%s, %s)",
            (text, utc_now_iso()),
        )
    db.commit()

    flash("Idea added to the vault.")
    return redirect(url_for("dashboard"))


@app.post("/ideas/<int:idea_id>/delete")
def delete_idea(idea_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM idea_vault WHERE id = %s", (idea_id,))
        idea = cur.fetchone()

        if not idea:
            flash("Idea not found.")
            return redirect(url_for("dashboard"))

        cur.execute("DELETE FROM idea_vault WHERE id = %s", (idea_id,))
    db.commit()

    flash("Idea deleted.")
    return redirect(url_for("dashboard"))


@app.post("/health")
def update_health():
    protein_value = safe_int(request.form.get("protein_value", 0), default=0, minimum=0)
    protein_goal = safe_int(request.form.get("protein_goal", 120), default=120, minimum=0)
    water_value = safe_int(request.form.get("water_value", 0), default=0, minimum=0)
    water_goal = safe_int(request.form.get("water_goal", 8), default=8, minimum=0)
    workout_done = 1 if request.form.get("workout_done") == "on" else 0
    reflection_text = request.form.get("reflection_text", "").strip()

    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM daily_log WHERE id = 1")
        before = cur.fetchone()

        xp_gain = 0
        if protein_goal > 0 and protein_value >= protein_goal and before["protein_value"] < before["protein_goal"]:
            xp_gain += 20
        if water_goal > 0 and water_value >= water_goal and before["water_value"] < before["water_goal"]:
            xp_gain += 10
        if workout_done and not before["workout_done"]:
            xp_gain += 30
        if reflection_text and not before["reflection_text"]:
            xp_gain += 15

        cur.execute(
            """
            UPDATE daily_log
            SET protein_goal = %s, protein_value = %s, water_goal = %s, water_value = %s, workout_done = %s, reflection_text = %s
            WHERE id = 1
            """,
            (protein_goal, protein_value, water_goal, water_value, workout_done, reflection_text),
        )
    db.commit()

    leveled, level, unlocked_outfits = add_xp(xp_gain)

    message = f"Health and reflection updated. XP earned: {xp_gain}."
    if leveled and xp_gain > 0:
        message += f" You leveled up to Level {level}!"
    if unlocked_outfits:
        message += " New outfit unlocked: " + ", ".join(unlocked_outfits) + "."

    flash(message)
    return redirect(url_for("dashboard"))


@app.post("/reset-day")
def reset_day():
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE daily_log SET protein_value = 0, water_value = 0, workout_done = 0, reflection_text = '' WHERE id = 1"
        )
    db.commit()

    flash("Daily health and reflection fields reset.")
    return redirect(url_for("dashboard"))


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
