import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('./api', () => ({
  getBase: () => 'http://127.0.0.1:8000',
  authHeaders: (headers: Record<string, string>) => headers,
}));

import { streamChat } from './sse';

afterEach(() => vi.unstubAllGlobals());

describe('local runtime chat', () => {
  it('sends stable session/request IDs to the same origin without the HUD secret', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('data: {"choices":[]}\n\ndata: [DONE]\n\n'));
    vi.stubGlobal('fetch', fetch);
    const events = [];
    for await (const event of streamChat({ model: 'local', messages: [{ role: 'user', content: 'teste' }], stream: true },
      undefined, { sessionId: 's1', requestId: 'p1' })) events.push(event);
    expect(events).toHaveLength(1);
    expect(fetch.mock.calls[0][0]).toBe('http://127.0.0.1:8000/v1/chat/completions');
    expect(fetch.mock.calls[0][1].headers).toMatchObject({ 'X-Jarvis-Session': 's1', 'X-Jarvis-Request': 'p1' });
    expect(fetch.mock.calls[0][1].headers['X-Jarvis-Token']).toBeUndefined();
  });

  it('stopping the request sends a matching cancel without repeating the command', async () => {
    const controller = new AbortController();
    const fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.endsWith('/v1/chat/completions')) {
        controller.abort();
        throw new DOMException('Cancelled', 'AbortError');
      }
      return new Response('{}');
    });
    vi.stubGlobal('fetch', fetch);
    const iterator = streamChat({ model: 'local', messages: [], stream: true }, controller.signal,
      { sessionId: 's1', requestId: 'p1' });
    await expect(iterator.next()).rejects.toThrow('Cancelled');
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetch.mock.calls[1][0]).toBe('http://127.0.0.1:8000/v1/runtime/cancel');
    expect(fetch.mock.calls[1][1].headers['X-Jarvis-Request']).toBe('p1');
  });
});
