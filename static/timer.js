let timerInterval = null;
let remainingSeconds = 25 * 60;
let activeMinutes = 25;

let selectedQuestId = localStorage.getItem("lifequest_selectedQuestId") || null;
let selectedQuestTitle = localStorage.getItem("lifequest_selectedQuestTitle") || "";

function saveTimerState() {
  localStorage.setItem("lifequest_selectedQuestId", selectedQuestId || "");
  localStorage.setItem("lifequest_selectedQuestTitle", selectedQuestTitle || "");
  localStorage.setItem("lifequest_remainingSeconds", String(remainingSeconds));
  localStorage.setItem("lifequest_activeMinutes", String(activeMinutes));
}

function loadTimerState() {
  const savedRemaining = parseInt(localStorage.getItem("lifequest_remainingSeconds") || "", 10);
  const savedActive = parseInt(localStorage.getItem("lifequest_activeMinutes") || "", 10);

  if (!Number.isNaN(savedRemaining)) remainingSeconds = savedRemaining;
  if (!Number.isNaN(savedActive)) activeMinutes = savedActive;
}

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
  saveTimerState();
}

function startTimer(minutes) {
  clearCurrentTimer();

  activeMinutes = minutes;
  remainingSeconds = minutes * 60;
  updateDisplay("✨");
  saveTimerState();

  timerInterval = setInterval(function () {
    remainingSeconds--;

    if (remainingSeconds <= 0) {
      clearCurrentTimer();
      remainingSeconds = 0;

      const display = document.getElementById("timer-display");
      if (display) {
        display.innerText = "DONE! ✨";
      }

      saveTimerState();

      if (selectedQuestTitle) {
        alert(`✨ Focus mission complete for: ${selectedQuestTitle}`);
      } else {
        alert("✨ Focus mission complete!");
      }

      return;
    }

    updateDisplay("✨");
    saveTimerState();
  }, 1000);
}

function pauseTimer() {
  clearCurrentTimer();
  updateDisplay("⏸");
  saveTimerState();
}

function resetTimer() {
  clearCurrentTimer();
  remainingSeconds = activeMinutes * 60;
  updateDisplay();
  saveTimerState();
}

document.addEventListener("DOMContentLoaded", function () {
  loadTimerState();
  updateDisplay();
  updateSelectedQuestUI();
});
