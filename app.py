from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "lifequest.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-change-me"

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


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
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
        id INTEGER PRIMARY KEY CHECK (id = 1),
        energy_mode TEXT NOT NULL DEFAULT 'normal',
        total_xp INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        notes TEXT DEFAULT '',
        campaign_id INTEGER,
        category TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'todo',
        xp_reward INTEGER NOT NULL DEFAULT 25,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
    );

    CREATE TABLE IF NOT EXISTS strategies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quest_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        completed INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (quest_id) REFERENCES quests(id)
    );

    CREATE TABLE IF NOT EXISTS idea_vault (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS daily_log (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        protein_goal INTEGER NOT NULL DEFAULT 120,
        protein_value INTEGER NOT NULL DEFAULT 0,
        water_goal INTEGER NOT NULL DEFAULT 8,
        water_value INTEGER NOT NULL DEFAULT 0,
        workout_done INTEGER NOT NULL DEFAULT 0,
        reflection_text TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS character_profile (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        character_name TEXT NOT NULL DEFAULT 'Terrabeacon Hero',
        current_outfit_id INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS outfit_store (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        slot TEXT NOT NULL DEFAULT 'outfit',
        rarity TEXT NOT NULL DEFAULT 'common',
        unlock_level INTEGER NOT NULL DEFAULT 1,
        xp_cost INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS owned_outfits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        outfit_id INTEGER NOT NULL UNIQUE,
        unlocked_at TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'level',
        FOREIGN KEY (outfit_id) REFERENCES outfit_store(id)
    );
    """

    with closing(sqlite3.connect(DB_PATH)) as db:
        db.executescript(schema)

        db.execute(
            "INSERT OR IGNORE INTO profile_settings (id, energy_mode, total_xp) VALUES (1, 'normal', 0)"
        )

        columns = [row[1] for row in db.execute("PRAGMA table_info(profile_settings)").fetchall()]
        if "level" not in columns:
            db.execute("ALTER TABLE profile_settings ADD COLUMN level INTEGER NOT NULL DEFAULT 1")
        if "current_xp" not in columns:
            db.execute("ALTER TABLE profile_settings ADD COLUMN current_xp INTEGER NOT NULL DEFAULT 0")
        if "daily_streak" not in columns:
            db.execute("ALTER TABLE profile_settings ADD COLUMN daily_streak INTEGER NOT NULL DEFAULT 0")
        if "last_activity_date" not in columns:
            db.execute("ALTER TABLE profile_settings ADD COLUMN last_activity_date TEXT")

        strategy_columns = [row[1] for row in db.execute("PRAGMA table_info(strategies)").fetchall()]
        if "completed" not in strategy_columns:
            db.execute("ALTER TABLE strategies ADD COLUMN completed INTEGER NOT NULL DEFAULT 0")

        db.execute(
            """
            UPDATE profile_settings
            SET
                level = COALESCE(level, 1),
                current_xp = COALESCE(current_xp, 0),
                daily_streak = COALESCE(daily_streak, 0)
            WHERE id = 1
            """
        )

        db.execute("INSERT OR IGNORE INTO daily_log (id) VALUES (1)")
        db.execute("INSERT OR IGNORE INTO character_profile (id) VALUES (1)")

        for name in CAMPAIGN_OPTIONS:
            db.execute("INSERT OR IGNORE INTO campaigns (name) VALUES (?)", (name,))

        for outfit in STARTER_OUTFITS:
            db.execute(
                """
                INSERT OR IGNORE INTO outfit_store (name, slot, rarity, unlock_level, xp_cost)
                VALUES (?, ?, ?, ?, ?)
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
    profile = db.execute("SELECT level FROM profile_settings WHERE id = 1").fetchone()
    level = profile["level"]

    eligible = db.execute(
        """
        SELECT id, name
        FROM outfit_store
        WHERE unlock_level <= ?
          AND id NOT IN (SELECT outfit_id FROM owned_outfits)
        ORDER BY unlock_level, id
        """,
        (level,),
    ).fetchall()

    unlocked_names = []
    for row in eligible:
        db.execute(
            """
            INSERT OR IGNORE INTO owned_outfits (outfit_id, unlocked_at, source)
            VALUES (?, ?, 'level')
            """,
            (row["id"], datetime.utcnow().isoformat()),
        )
        unlocked_names.append(row["name"])

    current = db.execute(
        "SELECT current_outfit_id FROM character_profile WHERE id = 1"
    ).fetchone()

    if current["current_outfit_id"] is None:
        first_owned = db.execute(
            """
            SELECT outfit_id
            FROM owned_outfits
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
        if first_owned:
            db.execute(
                "UPDATE character_profile SET current_outfit_id = ? WHERE id = 1",
                (first_owned["outfit_id"],),
            )

    db.commit()
    return unlocked_names


def get_character_data():
    db = get_db()

    character = db.execute("SELECT * FROM character_profile WHERE id = 1").fetchone()

    current_outfit = None
    if character and character["current_outfit_id"]:
        current_outfit = db.execute(
            "SELECT * FROM outfit_store WHERE id = ?",
            (character["current_outfit_id"],),
        ).fetchone()

    owned_outfits = db.execute(
        """
        SELECT os.*, oo.unlocked_at, oo.source
        FROM outfit_store os
        JOIN owned_outfits oo ON oo.outfit_id = os.id
        ORDER BY os.unlock_level, os.id
        """
    ).fetchall()

    return character, current_outfit, owned_outfits


def add_xp(amount):
    db = get_db()
    profile = db.execute(
        "SELECT level, current_xp FROM profile_settings WHERE id = 1"
    ).fetchone()

    old_level = profile["level"]
    level = old_level
    xp = profile["current_xp"] + amount
    leveled_up = False

    while xp >= level * 100:
        xp -= level * 100
        level += 1
        leveled_up = True

    db.execute(
        """
        UPDATE profile_settings
        SET level = ?, current_xp = ?, total_xp = total_xp + ?
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
    profile = db.execute(
        "SELECT daily_streak, last_activity_date FROM profile_settings WHERE id = 1"
    ).fetchone()

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

    db.execute(
        """
        UPDATE profile_settings
        SET daily_streak = ?, last_activity_date = ?
        WHERE id = 1
        """,
        (new_streak, today_str),
    )
    db.commit()

    return streak_bonus, new_streak, True


def get_campaign_progress():
    db = get_db()
    rows = db.execute(
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
    ).fetchall()

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

    settings = db.execute("SELECT * FROM profile_settings WHERE id = 1").fetchone()
    daily_log = db.execute("SELECT * FROM daily_log WHERE id = 1").fetchone()

    energy_mode = settings["energy_mode"]
    limits = ENERGY_PRESETS.get(energy_mode, ENERGY_PRESETS["normal"])

    quest_board = {}
    for category in CATEGORY_OPTIONS:
        limit = limits.get(category, 0)
        quest_board[category] = db.execute(
            """
            SELECT q.*, c.name AS campaign_name,
                   (SELECT COUNT(*) FROM strategies s WHERE s.quest_id = q.id) AS strategy_count
            FROM quests q
            LEFT JOIN campaigns c ON c.id = q.campaign_id
            WHERE q.status = 'todo' AND q.category = ?
            ORDER BY q.id ASC
            LIMIT ?
            """,
            (category, limit),
        ).fetchall()

    active_quests = db.execute(
        """
        SELECT q.*, c.name AS campaign_name
        FROM quests q
        LEFT JOIN campaigns c ON c.id = q.campaign_id
        WHERE q.status = 'todo'
        ORDER BY q.id DESC
        """
    ).fetchall()

    completed_quests = db.execute(
        """
        SELECT q.*, c.name AS campaign_name
        FROM quests q
        LEFT JOIN campaigns c ON c.id = q.campaign_id
        WHERE q.status = 'done'
        ORDER BY q.completed_at DESC
        LIMIT 20
        """
    ).fetchall()

    strategies = db.execute(
        """
        SELECT s.*, q.title AS quest_title
        FROM strategies s
        JOIN quests q ON q.id = s.quest_id
        WHERE q.status = 'todo'
        ORDER BY s.id
        """
    ).fetchall()

    campaigns = db.execute("SELECT * FROM campaigns ORDER BY name").fetchall()
    ideas = db.execute("SELECT * FROM idea_vault ORDER BY id DESC LIMIT 8").fetchall()
    campaign_progress = get_campaign_progress()
    character, current_outfit, owned_outfits = get_character_data()

    return render_template(
        "dashboard.html",
        profile=TRAIT_PROFILE,
        settings=settings,
        daily_log=daily_log,
        quest_board=quest_board,
        active_quests=active_quests,
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
    db.execute("UPDATE profile_settings SET energy_mode = ? WHERE id = 1", (energy_mode,))
    db.commit()
    flash(f"Energy mode set to {energy_mode}.")
    return redirect(url_for("dashboard"))


@app.post("/character/equip/<int:outfit_id>")
def equip_outfit(outfit_id):
    db = get_db()

    owned = db.execute(
        """
        SELECT os.*
        FROM outfit_store os
        JOIN owned_outfits oo ON oo.outfit_id = os.id
        WHERE os.id = ?
        """,
        (outfit_id,),
    ).fetchone()

    if not owned:
        flash("You don't own that outfit yet.")
        return redirect(url_for("dashboard"))

    db.execute(
        "UPDATE character_profile SET current_outfit_id = ? WHERE id = 1",
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
    cur = db.execute(
        """
        INSERT INTO quests (title, notes, campaign_id, category, status, xp_reward, created_at)
        VALUES (?, ?, ?, ?, 'todo', ?, ?)
        """,
        (title, notes, campaign_id, category, xp_reward, datetime.utcnow().isoformat()),
    )
    quest_id = cur.lastrowid

    strategy_lines = [s.strip() for s in strategies_raw.splitlines() if s.strip()]
    for line in strategy_lines:
        db.execute(
            "INSERT INTO strategies (quest_id, text, completed) VALUES (?, ?, 0)",
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
    quest = db.execute("SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()

    if not quest:
        flash("Quest not found.")
        return redirect(url_for("dashboard"))

    if quest["status"] == "done":
        flash("Quest already completed.")
        return redirect(url_for("dashboard"))

    total_gain = quest["xp_reward"]
    db.execute(
        "UPDATE quests SET status = 'done', completed_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), quest_id),
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

    quest = db.execute(
        "SELECT * FROM quests WHERE id = ?", (quest_id,)
    ).fetchone()

    if not quest:
        flash("Quest not found.")
        return redirect(url_for("dashboard"))

    db.execute("DELETE FROM strategies WHERE quest_id = ?", (quest_id,))
    db.execute("DELETE FROM quests WHERE id = ?", (quest_id,))
    db.commit()

    flash(f"Deleted quest: {quest['title']}.")
    return redirect(url_for("dashboard"))


@app.post("/strategies/<int:strategy_id>/complete")
def complete_strategy(strategy_id):
    db = get_db()

    strategy = db.execute(
        "SELECT * FROM strategies WHERE id = ?", (strategy_id,)
    ).fetchone()

    if not strategy:
        flash("Strategy not found.")
        return redirect(url_for("dashboard"))

    if strategy["completed"]:
        flash("Strategy already completed.")
        return redirect(url_for("dashboard"))

    db.execute(
        "UPDATE strategies SET completed = 1 WHERE id = ?",
        (strategy_id,),
    )
    db.commit()

    leveled, level, unlocked_outfits = add_xp(10)

    message = "Strategy completed! +10 XP."
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
    db.execute(
        "INSERT INTO idea_vault (text, created_at) VALUES (?, ?)",
        (text, datetime.utcnow().isoformat()),
    )
    db.commit()

    flash("Idea added to the vault.")
    return redirect(url_for("dashboard"))


@app.post("/ideas/<int:idea_id>/delete")
def delete_idea(idea_id):
    db = get_db()

    idea = db.execute(
        "SELECT * FROM idea_vault WHERE id = ?", (idea_id,)
    ).fetchone()

    if not idea:
        flash("Idea not found.")
        return redirect(url_for("dashboard"))

    db.execute("DELETE FROM idea_vault WHERE id = ?", (idea_id,))
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
    before = db.execute("SELECT * FROM daily_log WHERE id = 1").fetchone()

    xp_gain = 0
    if protein_goal > 0 and protein_value >= protein_goal and before["protein_value"] < before["protein_goal"]:
        xp_gain += 20
    if water_goal > 0 and water_value >= water_goal and before["water_value"] < before["water_goal"]:
        xp_gain += 10
    if workout_done and not before["workout_done"]:
        xp_gain += 30
    if reflection_text and not before["reflection_text"]:
        xp_gain += 15

    db.execute(
        """
        UPDATE daily_log
        SET protein_goal = ?, protein_value = ?, water_goal = ?, water_value = ?, workout_done = ?, reflection_text = ?
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
    db.execute(
        "UPDATE daily_log SET protein_value = 0, water_value = 0, workout_done = 0, reflection_text = '' WHERE id = 1"
    )
    db.commit()
    flash("Daily health and reflection fields reset.")
    return redirect(url_for("dashboard"))


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
    
