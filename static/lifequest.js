function getCampaignName(data, campaignId) {
  if (!campaignId) return "No campaign";
  const campaign = data.campaigns.find(c => String(c.id) === String(campaignId));
  return campaign ? campaign.name : "No campaign";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function getCurrentOutfit(data) {
  return data.outfits.find(o => o.id === data.character.current_outfit_id) || data.outfits[0];
}

function calculateCampaignProgress(data) {
  return data.campaigns.map(campaign => {
    const quests = data.quests.filter(q => String(q.campaign_id) === String(campaign.id));
    const total = quests.length;
    const completed = quests.filter(q => q.status === "done").length;
    const percent = total > 0 ? Math.round((completed / total) * 1000) / 10 : 0;

    return {
      ...campaign,
      total_quests: total,
      completed_quests: completed,
      percent
    };
  });
}

function renderProfile(data) {
  const level = data.profile.level || 1;
  const currentXp = data.profile.current_xp || 0;
  const totalXp = data.profile.total_xp || 0;
  const neededXp = level * 100;
  const percent = neededXp > 0 ? (currentXp / neededXp) * 100 : 0;

  document.getElementById("level-text").innerText = `Level ${level}`;
  document.getElementById("xp-text").innerText = `${currentXp} / ${neededXp} XP`;
  document.getElementById("xp-fill").style.width = `${Math.min(percent, 100)}%`;
  document.getElementById("total-xp-text").innerText = `Total XP: ${totalXp}`;

  const streak = data.profile.daily_streak || 0;
  document.getElementById("streak-pill").innerText = `🔥 Daily Streak: ${streak} day${streak === 1 ? "" : "s"}`;

  const lastActivity = data.profile.last_activity_date || "none";
  document.getElementById("last-activity-pill").innerText = `Last Activity: ${lastActivity}`;

  document.getElementById("energy-pill").innerText = `Energy: ${data.profile.energy_mode || "normal"}`;
  document.getElementById("energy_mode").value = data.profile.energy_mode || "normal";
}

function renderDailyLog(data) {
  const log = data.daily_log;

  document.getElementById("protein-summary").innerText = `${log.protein_value} / ${log.protein_goal}`;
  document.getElementById("water-summary").innerText = `${log.water_value} / ${log.water_goal}`;

  document.getElementById("protein_value").value = log.protein_value;
  document.getElementById("protein_goal").value = log.protein_goal;
  document.getElementById("water_value").value = log.water_value;
  document.getElementById("water_goal").value = log.water_goal;
  document.getElementById("workout_done").checked = !!log.workout_done;
  document.getElementById("reflection_text").value = log.reflection_text || "";
}

function renderTodayFocus(data) {
  const container = document.getElementById("today-focus-list");
  const todayQuests = data.quests.filter(q => q.status === "todo" && q.is_today);

  document.getElementById("today-count-pill").innerText = `${todayQuests.length} selected`;

  if (todayQuests.length === 0) {
    container.innerHTML = `<div class="muted">No quests in Today Focus yet. Add a few from the quest board below.</div>`;
    return;
  }

  container.innerHTML = todayQuests.map(quest => `
    <div class="quest" style="background:#fff7fc;">
      <div style="display:flex; justify-content:space-between; gap:10px; align-items:center;">
        <strong>${escapeHtml(quest.title)}</strong>
        <span class="pill">${quest.xp_reward} XP</span>
      </div>

      <div class="muted" style="margin-top:6px;">
        ${escapeHtml(getCampaignName(data, quest.campaign_id))} · ${escapeHtml(quest.category)}
      </div>

      ${(quest.strategies || []).map((strategy, index) => `
        <div style="margin-top:6px; padding-left:12px; border-left:3px solid #ffd8ee;">
          <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
            <span>${strategy.completed ? "✔" : "☐"} ${escapeHtml(strategy.text)}</span>
            ${
              strategy.completed
                ? `<span class="pill">Done</span>`
                : `<button type="button" class="btn-secondary" onclick="completeStrategy(${quest.id}, ${index})">+10 XP</button>`
            }
          </div>
        </div>
      `).join("")}

      ${quest.notes ? `<div style="margin-top:8px;">${escapeHtml(quest.notes)}</div>` : ""}

      <div class="actions-inline">
        <button type="button" class="btn-secondary" onclick="selectQuest('${quest.id}', ${JSON.stringify(quest.title)})">Focus Now</button>
        <button type="button" class="btn-secondary" onclick="toggleTodayQuest(${quest.id})">Remove from Today</button>
        <button type="button" onclick="completeQuest(${quest.id})">Complete Quest</button>
      </div>
    </div>
  `).join("");
}

function renderQuestBoard(data) {
  const container = document.getElementById("quest-board");
  const energyMode = data.profile.energy_mode || "normal";
  const limits = (typeof ENERGY_PRESETS !== "undefined" && ENERGY_PRESETS[energyMode])
    ? ENERGY_PRESETS[energyMode]
    : { main: 1, side: 1, stability: 1, reflection: 1, tiny: 1 };

  const categories = ["main", "side", "stability", "reflection", "tiny"];

  container.innerHTML = categories.map(category => {
    const quests = data.quests
      .filter(q => q.status === "todo" && q.category === category)
      .slice(0, limits[category] || 0);

    return `
      <div>
        <h3 style="margin-top:10px;">${category.charAt(0).toUpperCase() + category.slice(1)} Quest${quests.length === 1 ? "" : "s"}</h3>
        ${
          quests.length
            ? quests.map(quest => `
              <div class="quest">
                <div style="display:flex; justify-content:space-between; gap:10px; align-items:center;">
                  <strong>${escapeHtml(quest.title)}</strong>
                  <span class="pill">${quest.xp_reward} XP</span>
                </div>

                <div class="muted" style="margin-top:6px;">
                  ${escapeHtml(getCampaignName(data, quest.campaign_id))} · ${(quest.strategies || []).length} strategies
                  ${quest.is_today ? " · In Today Focus ✨" : ""}
                </div>

                ${(quest.strategies || []).map((strategy, index) => `
                  <div style="margin-top:6px; padding-left:12px; border-left:3px solid #ffd8ee;">
                    <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
                      <span>${strategy.completed ? "✔" : "☐"} ${escapeHtml(strategy.text)}</span>
                      ${
                        strategy.completed
                          ? `<span class="pill">Done</span>`
                          : `<button type="button" class="btn-secondary" onclick="completeStrategy(${quest.id}, ${index})">+10 XP</button>`
                      }
                    </div>
                  </div>
                `).join("")}

                ${quest.notes ? `<div style="margin-top:8px;">${escapeHtml(quest.notes)}</div>` : ""}

                <div class="actions-inline">
                  <button type="button" class="btn-secondary" onclick="selectQuest('${quest.id}', ${JSON.stringify(quest.title)})">Focus This Quest</button>
                  <button type="button" class="btn-secondary" onclick="toggleTodayQuest(${quest.id})">
                    ${quest.is_today ? "Remove from Today" : "Add to Today"}
                  </button>
                  <button type="button" onclick="completeQuest(${quest.id})">Complete Quest</button>
                  <button type="button" class="btn-danger" onclick="deleteQuest(${quest.id})">Delete</button>
                </div>
              </div>
            `).join("")
            : `<div class="muted">No ${category} quests showing in this energy mode.</div>`
        }
      </div>
    `;
  }).join("");
}

function renderActiveQuests(data) {
  const container = document.getElementById("active-quests-list");
  const activeQuests = data.quests.filter(q => q.status === "todo");

  if (activeQuests.length === 0) {
    container.innerHTML = `<div class="muted">No active quests yet.</div>`;
    return;
  }

  container.innerHTML = activeQuests.map(quest => `
    <div class="quest">
      <div style="display:flex; justify-content:space-between; gap:10px; align-items:center; flex-wrap:wrap;">
        <div>
          <strong>${escapeHtml(quest.title)}</strong>
          <div class="muted" style="margin-top:4px;">
            ${escapeHtml(getCampaignName(data, quest.campaign_id))} · ${escapeHtml(quest.category)} · ${quest.xp_reward} XP
            ${quest.is_today ? " · In Today Focus ✨" : ""}
          </div>
        </div>

        <button
          type="button"
          class="btn-secondary"
          onclick="toggleQuestPanel('quest-panel-${quest.id}', this)"
        >
          Show Strategies
        </button>
      </div>

      <div id="quest-panel-${quest.id}" style="display:none; margin-top:12px;">
        ${quest.notes ? `<div style="margin-top:8px;">${escapeHtml(quest.notes)}</div>` : ""}

        ${
          (quest.strategies || []).length > 0
            ? `
              <div style="margin-top:10px;" class="muted">Strategies:</div>
              ${(quest.strategies || []).map((strategy, index) => `
                <div style="margin-top:6px; padding-left:12px; border-left:3px solid #ffd8ee;">
                  <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
                    <span>${strategy.completed ? "✔" : "☐"} ${escapeHtml(strategy.text)}</span>
                    ${
                      strategy.completed
                        ? `<span class="pill">Done</span>`
                        : `<button type="button" class="btn-secondary" onclick="completeStrategy(${quest.id}, ${index})">+10 XP</button>`
                    }
                  </div>
                </div>
              `).join("")}
            `
            : `<div class="muted" style="margin-top:10px;">No strategies added yet.</div>`
        }

        <div class="actions-inline" style="margin-top:12px;">
          <button type="button" class="btn-secondary" onclick="selectQuest('${quest.id}', ${JSON.stringify(quest.title)})">Focus This Quest</button>
          <button type="button" class="btn-secondary" onclick="toggleTodayQuest(${quest.id})">
            ${quest.is_today ? "Remove from Today" : "Add to Today"}
          </button>
          <button type="button" onclick="completeQuest(${quest.id})">Complete Quest</button>
          <button type="button" class="btn-danger" onclick="deleteQuest(${quest.id})">Delete</button>
        </div>
      </div>
    </div>
  `).join("");
}

function renderCompletedQuests(data) {
  const container = document.getElementById("completed-quests-list");
  const completed = data.quests.filter(q => q.status === "done");

  if (completed.length === 0) {
    container.innerHTML = `<div class="muted">No completed quests yet.</div>`;
    return;
  }

  container.innerHTML = completed.map(quest => `
    <div class="quest">
      <div style="display:flex; justify-content:space-between; gap:10px; align-items:center;">
        <strong>${escapeHtml(quest.title)}</strong>
        <button type="button" class="btn-danger" onclick="deleteQuest(${quest.id})">Delete</button>
      </div>
      <div class="muted">
        ${escapeHtml(getCampaignName(data, quest.campaign_id))} · ${escapeHtml(quest.category)} · ${quest.xp_reward} XP
      </div>
      ${quest.notes ? `<div style="margin-top:6px;">${escapeHtml(quest.notes)}</div>` : ""}
    </div>
  `).join("");
}

function renderIdeas(data) {
  const container = document.getElementById("idea-list");

  if (!data.ideas.length) {
    container.innerHTML = `<div class="muted">No ideas saved yet.</div>`;
    return;
  }

  container.innerHTML = data.ideas.map(idea => `
    <div class="quest">
      <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start;">
        <span>${escapeHtml(idea.text)}</span>
        <button type="button" class="btn-danger" onclick="deleteIdea(${idea.id})">Delete</button>
      </div>
    </div>
  `).join("");
}

function renderOutfits(data) {
  const currentOutfit = getCurrentOutfit(data);

  document.getElementById("character-name").innerText = data.character.character_name || "Terrabeacon Hero";
  document.getElementById("current-outfit-rarity").innerText = currentOutfit ? capitalize(currentOutfit.rarity) : "Common";
  document.getElementById("current-outfit-name").innerText = currentOutfit
    ? `Current outfit: ${currentOutfit.name}`
    : "Current outfit: None equipped yet";

  const container = document.getElementById("outfit-list");
  const ownedOutfits = data.outfits.filter(o => o.owned);

  if (!ownedOutfits.length) {
    container.innerHTML = `<div class="muted">No outfits unlocked yet.</div>`;
    return;
  }

  container.innerHTML = ownedOutfits.map(outfit => `
    <div class="quest">
      <div style="display:flex; justify-content:space-between; gap:10px; align-items:center;">
        <strong>${escapeHtml(outfit.name)}</strong>
        <span class="pill">${capitalize(outfit.rarity)}</span>
      </div>

      <div class="muted" style="margin-top:6px;">
        Slot: ${escapeHtml(outfit.slot)} · Unlock level: ${outfit.unlock_level}
      </div>

      ${
        currentOutfit && outfit.id === currentOutfit.id
          ? `<div class="muted" style="margin-top:8px;">Currently equipped ✨</div>`
          : `<button type="button" style="margin-top:10px;" onclick="equipOutfit(${outfit.id})">Equip Outfit</button>`
      }
    </div>
  `).join("");
}

function renderCampaignProgress(data) {
  const container = document.getElementById("campaign-progress-list");
  const campaignProgress = calculateCampaignProgress(data);

  container.innerHTML = campaignProgress.map(campaign => `
    <div class="quest">
      <div style="display:flex; justify-content:space-between; gap:10px; align-items:center;">
        <strong>${escapeHtml(campaign.name)}</strong>
        <span class="pill">${campaign.completed_quests}/${campaign.total_quests} done</span>
      </div>

      <div style="margin-top:10px;">
        <div class="progress-bar">
          <div class="progress-fill" style="width:${campaign.percent}%;"></div>
        </div>
      </div>

      <div class="muted" style="margin-top:8px;">${campaign.percent}% complete</div>
    </div>
  `).join("");
}

function capitalize(value) {
  if (!value) return "";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function renderApp() {
  const data = getLifeQuestData();
  renderProfile(data);
  renderDailyLog(data);
  renderTodayFocus(data);
  renderQuestBoard(data);
  renderActiveQuests(data);
  renderCompletedQuests(data);
  renderIdeas(data);
  renderOutfits(data);
  renderCampaignProgress(data);
}

function toggleQuestPanel(panelId, button) {
  const panel = document.getElementById(panelId);
  if (!panel) return;

  if (panel.style.display === "none" || panel.style.display === "") {
    panel.style.display = "block";
    if (button) button.innerText = "Hide Strategies";
  } else {
    panel.style.display = "none";
    if (button) button.innerText = "Show Strategies";
  }
}

document.addEventListener("DOMContentLoaded", function () {
  renderApp();

  const addQuestForm = document.getElementById("add-quest-form");
  if (addQuestForm) {
    addQuestForm.addEventListener("submit", function (event) {
      event.preventDefault();

      addQuestFromForm({
        title: document.getElementById("quest-title").value,
        notes: document.getElementById("quest-notes").value,
        campaign_id: document.getElementById("quest-campaign").value,
        category: document.getElementById("quest-category").value,
        xp_reward: document.getElementById("quest-xp").value,
        strategies: document.getElementById("quest-strategies").value
      });
    });
  }

  const ideaForm = document.getElementById("idea-form");
  if (ideaForm) {
    ideaForm.addEventListener("submit", function (event) {
      event.preventDefault();
      addIdea(document.getElementById("idea-text").value);
    });
  }

  const healthForm = document.getElementById("health-form");
  if (healthForm) {
    healthForm.addEventListener("submit", function (event) {
      event.preventDefault();

      saveHealth({
        protein_value: document.getElementById("protein_value").value,
        protein_goal: document.getElementById("protein_goal").value,
        water_value: document.getElementById("water_value").value,
        water_goal: document.getElementById("water_goal").value,
        workout_done: document.getElementById("workout_done").checked,
        reflection_text: document.getElementById("reflection_text").value
      });
    });
  }

  const resetDayBtn = document.getElementById("reset-day-btn");
  if (resetDayBtn) {
    resetDayBtn.addEventListener("click", function () {
      resetDailyHealth();
    });
  }

  const energyForm = document.getElementById("energy-form");
  if (energyForm) {
    energyForm.addEventListener("submit", function (event) {
      event.preventDefault();
      const data = getLifeQuestData();
      data.profile.energy_mode = document.getElementById("energy_mode").value;
      saveLifeQuestData(data);
      renderApp();
    });
  }
});