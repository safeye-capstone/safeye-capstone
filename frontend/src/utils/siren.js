// 확정 위험 경보음. 소리 파일 없이 Web Audio로 두 음을 번갈아 낸다

const SIREN_SEC = 1.6;
const HIGH_HZ = 880;
const LOW_HZ = 660;
const VOLUME = 0.15;

let context = null;
let playingUntil = 0;

function getContext() {
  const AudioContextClass = window.AudioContext ?? window.webkitAudioContext;
  if (!AudioContextClass) return null;
  if (!context) context = new AudioContextClass();
  return context;
}

/**
 * 브라우저는 사용자가 페이지를 한 번 조작하기 전에는 소리를 막는다.
 * 첫 클릭·키 입력 때 불러서 풀어둔다.
 * 반환: 소리를 낼 수 있는 상태가 됐으면 true
 */
export async function unlockSiren() {
  const ctx = getContext();
  if (!ctx) return false;

  if (ctx.state === "suspended") {
    try {
      await ctx.resume();
    } catch {
      return false;
    }
  }
  return ctx.state === "running";
}

/**
 * 사이렌을 한 번 울린다. 이미 울리는 중이면 겹쳐 울리지 않는다.
 * 반환: 소리가 났으면(또는 이미 울리는 중이면) true, 브라우저가 막았으면 false
 */
export function playSiren() {
  const ctx = getContext();
  if (!ctx || ctx.state !== "running") return false;

  const now = ctx.currentTime;
  if (now < playingUntil) return true;
  playingUntil = now + SIREN_SEC;

  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();

  oscillator.type = "square";
  const step = SIREN_SEC / 4;
  for (let i = 0; i < 4; i += 1) {
    oscillator.frequency.setValueAtTime(
      i % 2 === 0 ? HIGH_HZ : LOW_HZ,
      now + i * step,
    );
  }

  // 시작과 끝에서 "틱" 소리가 나지 않게 음량을 부드럽게 올리고 내린다
  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.exponentialRampToValueAtTime(VOLUME, now + 0.03);
  gain.gain.setValueAtTime(VOLUME, now + SIREN_SEC - 0.1);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + SIREN_SEC);

  oscillator.connect(gain);
  gain.connect(ctx.destination);
  oscillator.start(now);
  oscillator.stop(now + SIREN_SEC);

  return true;
}
