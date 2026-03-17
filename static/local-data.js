const LIFEQUEST_STORAGE_KEY = "lifequest_local_save_v1";

const defaultLifeQuestData = {
  profile: {
    level: 1,
    current_xp: 0,
    total_xp: 0,
    daily_streak: 0,
    last_activity_date: null,
    energy_mode: "normal"
  },

  daily_log: {
    protein_goal: 120,
    protein_value: 0,
    water_goal: 8,
    water_value: 0,
    workout_done: false,
    reflection_text: ""
  },

  character: {
    character_name: "Terrabeacon Hero",
    current_outfit_id: 1
  },

  outfits: [
    { id: 1, name: "Pink Starter Fit", slot: "outfit", rarity: "common", unlock_level: 1, xp_cost: 0, owned: true },
    { id: 2, name: "Study Bunny Hoodie", slot: "outfit", rarity: "common", unlock_level: 2, xp_cost: 150, owned: false },
    { id: 3, name: "Cosmic Coder Jacket", slot: "outfit", rarity: "rare", unlock_level: 4, xp_cost: 400, owned: false },
    { id: 4, name: "Dream Mage Dress", slot: "outfit", rarity: "epic", unlock_level: 6, xp_cost: 800, owned: false }
  ],

  campaigns: [
    { id: 1, name: "The Knowledge Forge" },
    { id: 2, name: "The Symbolic Craft" },
    { id: 3, name: "The Digital Architect" },
    { id: 4, name: "The Signal Amplifier" },
    { id: 5, name: "The Grounding Cycle" }
  ],

  quests: [],

  ideas: []
};

function getLifeQuestData() {
  try {
    const raw = localStorage.getItem(LIFEQUEST_STORAGE_KEY);
    if (!raw) {
      localStorage.setItem(LIFEQUEST_STORAGE_KEY, JSON.stringify(defaultLifeQuestData));
      return JSON.parse(JSON.stringify(defaultLifeQuestData));
    }

    const parsed = JSON.parse(raw);

    return {
      ...JSON.parse(JSON.stringify(defaultLifeQuestData)),
      ...parsed,
      profile: { ...defaultLifeQuestData.profile, ...(parsed.profile || {}) },
      daily_log: { ...defaultLifeQuestData.daily_log, ...(parsed.daily_log || {}) },
      character: { ...defaultLifeQuestData.character, ...(parsed.character || {}) },
      outfits: parsed.outfits || JSON.parse(JSON.stringify(defaultLifeQuestData.outfits)),
      campaigns: parsed.campaigns || JSON.parse(JSON.stringify(defaultLifeQuestData.campaigns)),
      quests: parsed.quests || [],
      ideas: parsed.ideas || []
    };
  } catch (error) {
    console.error("Failed to load local LifeQuest data:", error);
    return JSON.parse(JSON.stringify(defaultLifeQuestData));
  }
}

function saveLifeQuestData(data) {
  localStorage.setItem(LIFEQUEST_STORAGE_KEY, JSON.stringify(data));
}

function exportLifeQuestSave() {
  const data = getLifeQuestData();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = "lifequest-save.json";
  a.click();

  URL.revokeObjectURL(url);
}

function importLifeQuestSave(file) {
  const reader = new FileReader();

  reader.onload = function (event) {
    try {
      const parsed = JSON.parse(event.target.result);
      saveLifeQuestData(parsed);
      location.reload();
    } catch (error) {
      alert("That file could not be imported.");
    }
  };

  reader.readAsText(file);
}

function resetLifeQuestSave() {
  const confirmed = confirm("Reset all local saved LifeQuest data on this browser?");
  if (!confirmed) return;

  localStorage.setItem(LIFEQUEST_STORAGE_KEY, JSON.stringify(defaultLifeQuestData));
  location.reload();
}

function addXp(amount) {
  const data = getLifeQuestData();

  let level = data.profile.level;
  let xp = data.profile.current_xp + amount;
  let leveledUp = false;

  while (xp >= level * 100) {
    xp -= level * 100;
    level += 1;
    leveledUp = true;
  }

  data.profile.level = level;
  data.profile.current_xp = xp;
  data.profile.total_xp += amount;

  unlockOutfitsForLevel(data);
  saveLifeQuestData(data);

  return { leveledUp, level };
}

function unlockOutfitsForLevel(data) {
  const level = data.profile.level;

  data.outfits = data.outfits.map(outfit => {
    if (outfit.unlock_level <= level) {
      return { ...outfit, owned: true };
    }
    return outfit;
  });

  const currentOwned = data.outfits.find(o => o.id === data.character.current_outfit_id && o.owned);
  if (!currentOwned) {
    const firstOwned = data.outfits.find(o => o.owned);
    if (firstOwned) {
      data.character.current_outfit_id = firstOwned.id;
    }
  }
}

function completeStrategy(questId, strategyIndex) {
  const data = getLifeQuestData();
  const quest = data.quests.find(q => q.id === questId);
  if (!quest) return;

  if (!quest.strategies || !quest.strategies[strategyIndex]) return;
  if (quest.strategies[strategyIndex].completed) return;

  quest.strategies[strategyIndex].completed = true;
  saveLifeQuestData(data);
  addXp(10);
  location.reload();
}

function completeQuest(questId) {
  const data = getLifeQuestData();
  const quest = data.quests.find(q => q.id === questId);
  if (!quest) return;

  if (quest.status === "done") return;

  quest.status = "done";
  quest.completed_at = new Date().toISOString();
  quest.is_today = false;

  saveLifeQuestData(data);
  addXp(Number(quest.xp_reward || 25));
  location.reload();
}

function deleteQuest(questId) {
  const data = getLifeQuestData();
  data.quests = data.quests.filter(q => q.id !== questId);
  saveLifeQuestData(data);
  location.reload();
}

function toggleTodayQuest(questId) {
  const data = getLifeQuestData();
  const quest = data.quests.find(q => q.id === questId);
  if (!quest) return;

  quest.is_today = !quest.is_today;
  saveLifeQuestData(data);
  location.reload();
}

function equipOutfit(outfitId) {
  const data = getLifeQuestData();
  const outfit = data.outfits.find(o => o.id === outfitId && o.owned);
  if (!outfit) return;

  data.character.current_outfit_id = outfitId;
  saveLifeQuestData(data);
  location.reload();
}

function addIdea(text) {
  const clean = (text || "").trim();
  if (!clean) return;

  const data = getLifeQuestData();
  data.ideas.unshift({
    id: Date.now(),
    text: clean,
    created_at: new Date().toISOString()
  });

  saveLifeQuestData(data);
  location.reload();
}

function deleteIdea(ideaId) {
  const data = getLifeQuestData();
  data.ideas = data.ideas.filter(i => i.id !== ideaId);
  saveLifeQuestData(data);
  location.reload();
}

function saveHealth(formValues) {
  const data = getLifeQuestData();

  data.daily_log.protein_value = Number(formValues.protein_value || 0);
  data.daily_log.protein_goal = Number(formValues.protein_goal || 120);
  data.daily_log.water_value = Number(formValues.water_value || 0);
  data.daily_log.water_goal = Number(formValues.water_goal || 8);
  data.daily_log.workout_done = !!formValues.workout_done;
  data.daily_log.reflection_text = formValues.reflection_text || "";

  saveLifeQuestData(data);
  location.reload();
}

function resetDailyHealth() {
  const data = getLifeQuestData();
  data.daily_log.protein_value = 0;
  data.daily_log.water_value = 0;
  data.daily_log.workout_done = false;
  data.daily_log.reflection_text = "";
  saveLifeQuestData(data);
  location.reload();
}

function addQuestFromForm(formValues) {
  const title = (formValues.title || "").trim();
  if (!title) {
    alert("Quest title is required.");
    return;
  }

  const strategies = (formValues.strategies || "")
    .split("\n")
    .map(s => s.trim())
    .filter(Boolean)
    .map(text => ({ text, completed: false }));

  const data = getLifeQuestData();

  const quest = {
    id: Date.now(),
    title,
    notes: (formValues.notes || "").trim(),
    campaign_id: formValues.campaign_id ? Number(formValues.campaign_id) : null,
    category: formValues.category || "side",
    status: "todo",
    xp_reward: Number(formValues.xp_reward || 25),
    created_at: new Date().toISOString(),
    completed_at: null,
    is_today: false,
    strategies
  };

  data.quests.unshift(quest);
  saveLifeQuestData(data);

  if (strategies.length > 0) {
    addXp(strategies.length * 10);
  }

  location.reload();
}