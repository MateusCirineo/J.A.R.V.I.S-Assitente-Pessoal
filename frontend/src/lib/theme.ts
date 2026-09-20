import type { ThemeMode } from './store';

type ClassTarget = Pick<DOMTokenList, 'add' | 'remove'>;

const THEMES: readonly ThemeMode[] = ['light', 'dark', 'system', 'hud'];

/**
 * Theme requested through `?tema=` (used by the HUD runtime when it opens the
 * chat window). Returns null for a missing or unknown value.
 */
export function themeFromUrl(search: string): ThemeMode | null {
  const value = new URLSearchParams(search).get('tema');
  return value && (THEMES as readonly string[]).includes(value) ? (value as ThemeMode) : null;
}

/**
 * Apply the theme classes to <html>. Shared by the pre-render pass in
 * main.tsx and the settings effect in App.tsx so the two never drift.
 *
 * `hud` is a dark theme: it keeps the `dark` class so every `dark:` variant
 * and dark token still applies, and adds `hud` for the overrides on top.
 */
export function applyThemeClass(
  theme: ThemeMode | string | undefined,
  target: ClassTarget = document.documentElement.classList,
): void {
  target.remove('dark', 'light', 'hud');
  if (theme === 'dark') target.add('dark');
  else if (theme === 'light') target.add('light');
  else if (theme === 'hud') target.add('dark', 'hud');
}
