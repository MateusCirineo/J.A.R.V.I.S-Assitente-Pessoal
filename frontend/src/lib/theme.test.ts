import { describe, expect, it } from 'vitest';
import { applyThemeClass, themeFromUrl } from './theme';

describe('themeFromUrl', () => {
  it('accepts only known themes', () => {
    expect(themeFromUrl('?tema=hud')).toBe('hud');
    expect(themeFromUrl('?x=1&tema=dark')).toBe('dark');
    expect(themeFromUrl('?tema=neon')).toBeNull();
    expect(themeFromUrl('')).toBeNull();
  });
});

function fakeClassList() {
  const set = new Set<string>();
  return {
    add: (...c: string[]) => c.forEach((x) => set.add(x)),
    remove: (...c: string[]) => c.forEach((x) => set.delete(x)),
    list: () => [...set].sort(),
  };
}

describe('applyThemeClass', () => {
  it('keeps dark variants active under the HUD theme', () => {
    const cl = fakeClassList();
    applyThemeClass('hud', cl);
    expect(cl.list()).toEqual(['dark', 'hud']);
  });

  it('removes the HUD overrides when switching back to an original theme', () => {
    const cl = fakeClassList();
    applyThemeClass('hud', cl);
    applyThemeClass('light', cl);
    expect(cl.list()).toEqual(['light']);
    applyThemeClass('dark', cl);
    expect(cl.list()).toEqual(['dark']);
  });

  it('leaves no theme class for system so the OS preference decides', () => {
    const cl = fakeClassList();
    applyThemeClass('hud', cl);
    applyThemeClass('system', cl);
    expect(cl.list()).toEqual([]);
  });
});
