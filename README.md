# tts-studio

Text-to-speech jobs rendered by GitHub Actions with Microsoft Edge neural voices (`edge-tts`).

1. Add or edit `jobs/<name>/script.json`.
2. Push. The **TTS render** workflow writes one MP3 per line to `jobs/<name>/out/` and commits it back.

Voices: `zh-TW-HsiaoChenNeural` (女), `zh-TW-HsiaoYuNeural` (女), `zh-TW-YunJheNeural` (男).
A line can be `{"text": "字幕文字", "say": "實際念的文字"}` to fix pronunciation without changing subtitles.

## z1 流年有聲影片

1. 在 z1（kftseng2oo1.github.io/z1）的「流年運勢診斷 → 🎬 流年動畫旁白・分享下載」按 **🎙 有聲版工作檔**，得到 `flow.json`。
2. 在本 repo 建立資料夾 `jobs/<自訂名稱>/`，把 `flow.json` 上傳進去（GitHub 網頁：Add file → Upload files）。
3. **z1 流年有聲影片** workflow 會自動：
   - 開啟線上 z1、依 `flow.json` 排盤並產生旁白
   - 用 edge-tts（`voice`，預設 `zh-TW-HsiaoChenNeural`）念出每一句
   - 依實際語音長度逐格畫出動畫，合成字幕燒入的有聲 MP4
4. 約 5–10 分鐘後到 `jobs/<自訂名稱>/out/` 下載 `flow.mp4`（另有 `flow.m4a` 純旁白、`flow.srt` 字幕）。

`flow.json` 可改 `voice`（男聲 `zh-TW-YunJheNeural`）或 `rate`（例如 `"+10%"`）後重新上傳，即會重新產生。
本地測試（不連微軟語音）：`FLOW_FAKE_TTS=1 CHROME_PATH=/path/to/chrome python flow.py <job>`
