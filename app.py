import os
from flask import Flask, render_template

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


@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        profile=TRAIT_PROFILE,
        energy_presets=ENERGY_PRESETS,
        campaign_options=CAMPAIGN_OPTIONS,
        category_options=CATEGORY_OPTIONS,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
