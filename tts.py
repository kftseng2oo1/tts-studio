"""Render every jobs/<name>/script.json whose content changed into per-line MP3s.

script.json: {"voice": "...", "rate": "+0%", "pitch": "+0Hz",
              "scenes": [["line", ...], ...]}       # a line may also be {"text": "...", "say": "..."}
Output:      jobs/<name>/out/SS_LL.mp3 (+ SS_LL.txt with the subtitle text) and out/.hash
"""
import asyncio, hashlib, json, pathlib, shutil, sys
import edge_tts

async def render(job_dir: pathlib.Path, force: bool):
    spec_path = job_dir / "script.json"
    raw = spec_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    out = job_dir / "out"
    if not force and (out / ".hash").exists() and (out / ".hash").read_text().strip() == digest:
        print(f"skip {job_dir.name} (unchanged)")
        return False
    spec = json.loads(raw)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    voice, rate, pitch = spec.get("voice", "zh-TW-HsiaoChenNeural"), spec.get("rate", "+0%"), spec.get("pitch", "+0Hz")
    for si, lines in enumerate(spec["scenes"]):
        for li, line in enumerate(lines):
            text = line["text"] if isinstance(line, dict) else line
            say = line.get("say", text) if isinstance(line, dict) else line
            stem = out / f"{si:02d}_{li:02d}"
            for attempt in range(4):
                try:
                    await edge_tts.Communicate(say, voice, rate=rate, pitch=pitch).save(str(stem) + ".mp3")
                    break
                except Exception as e:  # transient websocket errors
                    print("retry", stem.name, e); await asyncio.sleep(3 * (attempt + 1))
            else:
                sys.exit(f"failed: {stem.name}")
            stem.with_suffix(".txt").write_text(text, encoding="utf-8")
            print("ok", stem.name, text)
    (out / ".hash").write_text(digest)
    return True

async def main():
    force = "--force" in sys.argv
    names = [a for a in sys.argv[1:] if not a.startswith("--")]
    jobs = [pathlib.Path("jobs") / n for n in names] if names else sorted(p.parent for p in pathlib.Path("jobs").glob("*/script.json"))
    for j in jobs:
        await render(j, force)

asyncio.run(main())
