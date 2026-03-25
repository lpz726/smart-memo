/**
 * Smart Memo — 语音输入与播报模块
 */

// ── 语音输入 ────────────────────────────────────────────────────────────────

let recognition = null;
let isListening = false;

export function initVoice(onResult, onError) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return false;

  recognition = new SpeechRecognition();
  recognition.lang = 'zh-CN';
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onresult = (e) => {
    const text = e.results[0][0].transcript;
    onResult(text);
  };
  recognition.onerror = (e) => onError(e.error);
  recognition.onend = () => { isListening = false; };

  return true;
}

export function toggleVoice(btnEl, statusEl, statusTextEl) {
  if (!recognition) {
    statusTextEl.textContent = '浏览器不支持语音输入';
    statusEl.className = 'voice-status show listening';
    return;
  }
  if (isListening) {
    recognition.stop();
    isListening = false;
    btnEl.classList.remove('listening');
    statusEl.classList.remove('show');
  } else {
    recognition.start();
    isListening = true;
    btnEl.classList.add('listening');
    statusEl.className = 'voice-status show listening';
    statusTextEl.textContent = '正在聆听...';
  }
}

// ── 行程播报 ────────────────────────────────────────────────────────────────

let utterances = [];
let currentIdx = 0;
let paused = false;

export function startBroadcast(schedules, { rate = 1, volume = 1 } = {}) {
  window.speechSynthesis.cancel();
  utterances = [];
  currentIdx = 0;
  paused = false;

  if (!schedules.length) return false;

  for (const s of schedules) {
    const text = s.time_slot
      ? `${s.time_slot}，${s.title}。${s.description || ''}`
      : `${s.title}。${s.description || ''}`;

    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'zh-CN';
    u.rate = rate;
    u.volume = volume;
    utterances.push(u);
  }

  speakAt(0);
  return true;
}

function speakAt(idx) {
  if (idx >= utterances.length) return;
  currentIdx = idx;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterances[idx]);
  utterances[idx].onend = () => speakAt(idx + 1);
}

export function pauseBroadcast() {
  if (window.speechSynthesis.speaking) {
    window.speechSynthesis.pause();
    paused = true;
  }
}

export function resumeBroadcast() {
  window.speechSynthesis.resume();
  paused = false;
}

export function stopBroadcast() {
  window.speechSynthesis.cancel();
  paused = false;
}

export function nextItem() { speakAt(Math.min(currentIdx + 1, utterances.length - 1)); }
export function prevItem() { speakAt(Math.max(currentIdx - 1, 0)); }

export function isPaused() { return paused; }
export function getProgress() {
  if (!utterances.length) return 0;
  return Math.round((currentIdx / utterances.length) * 100);
}
