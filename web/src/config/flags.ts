// ponytail: no document names the value that turns a flag off. "off" is the working value; change it here if the deploy uses another one.
const FLAG_OFF = "off";

/** An empty base sends API requests to the origin that serves the app. */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export const IS_LIVE_BOARD_ON = process.env.NEXT_PUBLIC_LIVE_BOARD !== FLAG_OFF;

export const IS_CHAT_SHOWN = process.env.NEXT_PUBLIC_SHOW_CHAT !== FLAG_OFF;
