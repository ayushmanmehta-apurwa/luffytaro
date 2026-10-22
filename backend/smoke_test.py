"""Check your Nebius Token Factory settings BEFORE turning on live mode.

    cd backend
    python smoke_test.py

It makes three tiny calls (reasoning model, vision model with a generated photo, JSON output) and prints the latency of each.
Nothing here is mocked: if it fails, the message tells you what to fix. With no key configured it only explains what is missing.
"""
import base64
import time

from app import config, samples


def main():
    print('Base URL :', config.NEBIUS_BASE_URL)
    print('Key set  :', bool(config.NEBIUS_API_KEY))
    print('Models   : fast =', config.FAST_MODEL or '(missing)', '| vision =', config.VISION_MODEL or '(missing)', '| reasoning =', config.REASON_MODEL or '(missing)')
    if not (config.NEBIUS_API_KEY and config.FAST_MODEL and config.REASON_MODEL):
        print('\nLive mode is OFF (Demo Mode). Set NEBIUS_API_KEY, FAST_MODEL and REASON_MODEL in backend/.env to test the real API.')
        print('Copy the exact model IDs from the Token Factory model list (or Playground > "view as code").')
        return 0
    from app.llm import get_client
    client = get_client()

    def call(label, model, content, max_tokens=600):
        t = time.time()
        try:
            r = client.chat.completions.create(model=model, messages=[{'role': 'user', 'content': content}], temperature=0.0, max_tokens=max_tokens)
            text = (r.choices[0].message.content or '').strip().replace(chr(10), ' ')
            print('[ok]  %-9s %5.2fs  tokens=%s  -> %s' % (label, time.time() - t, getattr(r.usage, 'total_tokens', '?'), text[:110]))
            return True
        except Exception as e:
            print('[FAIL] %-9s %s: %s' % (label, type(e).__name__, str(e)[:300]))
            return False

    ok = call('reasoning', config.REASON_MODEL, 'Reply with the single word: ready')
    jpeg = samples.scene_jpeg('broken_light', False, 1)
    b64 = base64.b64encode(jpeg).decode()
    ok &= call('vision', config.VISION_MODEL, [{'type': 'text', 'text': 'Is the light in this picture switched on? Answer yes or no and say why in one sentence.'},
                                              {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}}])
    ok &= call('json', config.FAST_MODEL, 'Return only a JSON object with the key status set to ok.')
    print('\nAll calls worked. You can leave FORCE_DEMO_MODE unset and start the app in live mode.' if ok else
          '\nFix the failing call(s) above. Reasoning models may print thinking text first; the app strips it and validates JSON.')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
