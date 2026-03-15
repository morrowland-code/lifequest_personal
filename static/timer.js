let timerInterval = null;
let remainingSeconds = 25 * 60;
let activeMinutes = 25;
let selectedQuestId = null;
let selectedQuestTitle = "";

function updateDisplay(label = "") {
  const display = document.getElementById("timer-display");
  if (!display) return;

  const min = Math.floor(remainingSeconds / 60);
  const sec = remainingSeconds % 60;
  const timeText = `${min}:${sec.toString().padStart(2, "0")}`;

  display.innerText = label ? `${timeText} ${label}` : timeText;
}

function updateSelectedQuestUI() {
  const questBox = document.getElementById("selected-quest");
  if (!questBox) return;

  if (selectedQuestTitle) {
    questBox.innerText = `Focused Quest: ${selectedQuestTitle}`;
  } else {
    questBox.innerText = "Focused Quest: none selected";
  }
}

function clearCurrentTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
}

function selectQuest(questId, questTitle) {
  selectedQuestId = questId;
  selectedQuestTitle = questTitle || "";
  updateSelectedQuestUI();
}

function startTimer(minutes) {
  clearCurrentTimer();

  activeMinutes = minutes;
  remainingSeconds = minutes * 60;
  updateDisplay("✨");

  timerInterval = setInterval(function () {
    remainingSeconds--;

    if (remainingSeconds <= 0) {
      clearCurrentTimer();
      remainingSeconds = 0;

      const display = document.getElementById("timer-display");
      if (display) {
        display.innerText = "DONE! ✨";
      }

      if (selectedQuestTitle) {
        alert(`✨ Focus mission complete for: ${selectedQuestTitle}`);
      } else {
        alert("✨ Focus mission complete! Claim your XP by completing the quest.");
      }

      return;
    }

    updateDisplay("✨");
  }, 1000);
}

function pauseTimer() {
  clearCurrentTimer();
  updateDisplay("⏸");
}

function resetTimer() {
  clearCurrentTimer();
  remainingSeconds = activeMinutes * 60;
  updateDisplay();
}

document.addEventListener("DOMContentLoaded", function () {
  updateDisplay();
  updateSelectedQuestUI();
});