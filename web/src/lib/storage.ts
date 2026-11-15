/**
 * Browser storage holds only the language and this session ID. The shell stores
 * the language (components/shell/language-choice.ts).
 */
const SESSION_ID_KEY = "boramae.session";
const SESSION_ID_BYTES = 16;

/**
 * The random ID of this tab. It names no person, and it only counts model calls
 * against the session budget. With blocked storage the ID lasts for one page
 * load.
 */
export function readSessionId(): string {
  const stored = readStored();
  if (stored) {
    return stored;
  }
  const sessionId = createSessionId();
  try {
    window.sessionStorage.setItem(SESSION_ID_KEY, sessionId);
  } catch {
    // Blocked or full storage: the ID then lives in the client store only.
  }
  return sessionId;
}

function readStored(): string | null {
  try {
    return window.sessionStorage.getItem(SESSION_ID_KEY);
  } catch {
    // Blocked storage, or the static build, which has no window: nothing is stored.
    return null;
  }
}

/** 32 hex characters, inside the session ID form of docs/BUILD_CONTRACT.md. */
function createSessionId(): string {
  // Not crypto.randomUUID: it exists only in a secure context, and the offline
  // demo can run on plain HTTP from another machine on the local network.
  const bytes = crypto.getRandomValues(new Uint8Array(SESSION_ID_BYTES));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}
