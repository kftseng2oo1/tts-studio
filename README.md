# tts-studio

Text-to-speech jobs rendered by GitHub Actions with Microsoft Edge neural voices (`edge-tts`).

1. Add or edit `jobs/<name>/script.json`.
2. Push. The **TTS render** workflow writes one MP3 per line to `jobs/<name>/out/` and commits it back.

Voices: `zh-TW-HsiaoChenNeural` (女), `zh-TW-HsiaoYuNeural` (女), `zh-TW-YunJheNeural` (男).
A line can be `{"text": "字幕文字", "say": "實際念的文字"}` to fix pronunciation without changing subtitles.
