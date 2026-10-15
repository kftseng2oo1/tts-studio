"""z1 流年動畫有聲版：jobs/<name>/flow.json → jobs/<name>/out/flow.mp4（台灣口音旁白，字幕燒入）

流程：
  1. flow_video.mjs script  以網站目前版本產生旁白句子
  2. edge-tts               每句一個 MP3，量出實際長度
  3. flow_video.mjs render  依實際長度逐格畫出動畫（JPEG 串流）→ ffmpeg 編碼
  4. ffmpeg                 依時間軸把每句語音放到正確位置，與畫面合成 MP4
另輸出 out/flow.srt（實際時間軸字幕）與 out/flow.m4a（純旁白）。
"""
import asyncio, hashlib, json, os, pathlib, shutil, subprocess, sys
import edge_tts

FPS = 24


def run(cmd, **kw):
    print('+', ' '.join(map(str, cmd)), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def probe_seconds(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                          '-of', 'default=nw=1:nk=1', str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


async def tts_all(sents, voice, rate, out_dir):
    paths = []
    fake = os.environ.get('FLOW_FAKE_TTS') == '1'   # 本地測試用：以音調代替 TTS
    for i, text in enumerate(sents):
        p = out_dir / f'{i:03d}.mp3'
        if fake:
            sec = max(1.0, len(text) / 4.8)
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i',
                            f'sine=frequency={300 + 40 * (i % 8)}:duration={sec:.2f}', str(p)], check=True)
            paths.append(p)
            continue
        for attempt in range(4):
            try:
                await edge_tts.Communicate(text, voice, rate=rate).save(str(p))
                break
            except Exception as e:  # 偶發 websocket 錯誤
                print('retry', i, e, flush=True)
                await asyncio.sleep(3 * (attempt + 1))
        else:
            sys.exit(f'TTS failed: {text}')
        paths.append(p)
    return paths


def srt_time(s):
    ms = round(s * 1000)
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


def render_job(job_dir: pathlib.Path, force: bool):
    spec_path = job_dir / 'flow.json'
    raw = spec_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    out = job_dir / 'out'
    stamp = out / '.flowhash'
    if not force and stamp.exists() and stamp.read_text().strip() == digest:
        print(f'skip {job_dir.name} (unchanged)')
        return
    job = json.loads(raw)
    if job.get('type') != 'z1-flow':
        sys.exit(f'{spec_path}: not a z1-flow job')
    out.mkdir(parents=True, exist_ok=True)
    work = job_dir / '.work'
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()

    # 1. 旁白句子（以網站目前版本為準）
    run(['node', 'flow_video.mjs', 'script', spec_path, work / 'sents.json'])
    sents = json.loads((work / 'sents.json').read_text(encoding='utf-8'))
    if job.get('sentences') and job['sentences'] != sents:
        print('note: 網站版本的旁白與工作檔略有不同，以網站目前版本為準', flush=True)

    # 2. TTS
    voice = job.get('voice', 'zh-TW-HsiaoChenNeural')
    rate = job.get('rate', '+0%')
    mp3s = asyncio.run(tts_all(sents, voice, rate, work))
    durs = [probe_seconds(p) for p in mp3s]
    (work / 'durs.json').write_text(json.dumps(durs))

    # 3. 逐格畫面 → 無聲影片
    silent = work / 'silent.mp4'
    with open(work / 'timeline.json', 'w') as tl:
        node = subprocess.Popen(['node', 'flow_video.mjs', 'render', spec_path, work / 'durs.json', str(FPS)],
                                stdout=subprocess.PIPE, stderr=tl)
        run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg',
             '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-pix_fmt', 'yuv420p',
             '-movflags', '+faststart', silent], stdin=node.stdout)
        node.stdout.close()
        if node.wait() != 0:
            sys.exit('render failed')
    timeline = None
    for line in (work / 'timeline.json').read_text().splitlines():
        if line.startswith('{"total"'):
            timeline = json.loads(line)
        elif line.strip():
            print(line)
    if not timeline:
        sys.exit('no timeline from renderer')

    # 4. 旁白音軌：每句延遲到它的起點後混音
    inputs, filters = [], []
    for i, (p, s) in enumerate(zip(mp3s, timeline['sents'])):
        inputs += ['-i', p]
        ms = round(s['start'] * 1000)
        filters.append(f'[{i}:a]aresample=44100,adelay={ms}|{ms}[a{i}]')
    mix = ''.join(f'[a{i}]' for i in range(len(mp3s)))
    filters.append(f'{mix}amix=inputs={len(mp3s)}:normalize=0:dropout_transition=0,'
                   f'apad,atrim=0:{timeline["total"] + 0.5:.3f}[aout]')
    narr = out / 'flow.m4a'
    run(['ffmpeg', '-y', '-loglevel', 'error', *inputs, '-filter_complex', ';'.join(filters),
         '-map', '[aout]', '-c:a', 'aac', '-b:a', '128k', narr])

    # 5. 合成
    final = out / 'flow.mp4'
    run(['ffmpeg', '-y', '-loglevel', 'error', '-i', silent, '-i', narr, '-map', '0:v', '-map', '1:a',
         '-c:v', 'copy', '-c:a', 'copy', '-shortest', '-movflags', '+faststart', final])

    # 字幕（實際時間軸）
    srt = '\n'.join(f"{i + 1}\n{srt_time(s['start'])} --> {srt_time(s['start'] + s['dur'])}\n{s['text']}\n"
                    for i, s in enumerate(timeline['sents']))
    (out / 'flow.srt').write_text('﻿' + srt, encoding='utf-8')

    shutil.rmtree(work, ignore_errors=True)
    stamp.write_text(digest)
    print(f'done {job_dir.name}: {final} ({final.stat().st_size / 1e6:.1f} MB, {timeline["total"]:.1f}s)', flush=True)


def main():
    force = '--force' in sys.argv
    names = [a for a in sys.argv[1:] if not a.startswith('--')]
    jobs = [pathlib.Path('jobs') / n for n in names] if names else \
        sorted(p.parent for p in pathlib.Path('jobs').glob('*/flow.json'))
    for j in jobs:
        render_job(j, force)


if __name__ == '__main__':
    main()
