import { isTauri } from './api';

// Local HUD runtime (modo-show/jarvis_runtime.py), a separate process from the
// OpenJarvis server. Chat commands reach it through the same-origin server
// bridge; the runtime token never goes to this frontend. If it is down, the opened
// window shows the browser's connection error.
export const HUD_RUNTIME_URL = 'http://127.0.0.1:8765';

export type HudView = 'painel' | 'jarvis';

export async function openHudView(view: HudView): Promise<void> {
  const url = `${HUD_RUNTIME_URL}/${view}`;
  if (isTauri()) {
    const { open } = await import('@tauri-apps/plugin-shell');
    await open(url);
    return;
  }
  // A named target reuses the same window on repeated clicks instead of
  // stacking new ones.
  window.open(url, `jarvis-${view}`, 'popup,width=1180,height=780');
}
