---
name: video-download
description: This skill should be used when the user pastes a video or social media post link (X/Twitter, YouTube, Bilibili, etc.) and asks to download, save, or extract audio from it (e.g. "下载这个视频", "download this", "保存视频", "只要音频"). It runs a bundled yt-dlp wrapper that handles proxy detection, format selection, resume, and verification in a single command, minimizing token usage.
agent_created: true
---

# Video Download

One command to download a video from a URL. The bundled script auto-detects a working proxy (cached per host), picks the best muxed format, resumes on failure, and verifies the result with ffprobe. Do not load the heavier `social-video-downloader` skill for routine downloads — use this one.

## Workflow

Run the bundled script directly. `<skill-dir>` is this skill's base directory.

```bash
python "<skill-dir>/scripts/video_downloader.py" "<url>" --out "<workspace>/output"
```

- Always pass `--out` explicitly (e.g. `<workspace>/output`); the script's built-in default points to its own directory.
- The script prints `[代理]` (chosen proxy), `[画质]` (chosen format), `完成：<path>` and `[校验]` (ffprobe stream info). Report the final path, resolution, and duration from these lines — no extra verification commands needed.
- For videos longer than ~10 minutes, run with `run_in_background` and read the tail output when notified; the script resumes automatically after network errors.

## Common flags

```bash
python "<skill-dir>/scripts/video_downloader.py" "<url>" --quality 720   # cap resolution
python "<skill-dir>/scripts/video_downloader.py" "<url>" --audio         # MP3 only, saved as *-audio.mp3
python "<skill-dir>/scripts/video_downloader.py" "<url>" --list          # list formats only
python "<skill-dir>/scripts/video_downloader.py" "<url>" --cookies edge  # login-gated content
python "<skill-dir>/scripts/video_downloader.py" "<url>" --proxy http://127.0.0.1:3067  # force proxy
```


## Failure handling

- `yt-dlp not found` → `python -m pip install -U yt-dlp`.
- Extraction breaks after a platform change → upgrade yt-dlp first (`python -m pip install -U yt-dlp`), retry once.
- All proxy candidates fail → ask the user for their current proxy; do not loop retries.
- Downloaded-but-silent or missing audio → re-run with `-f "bv+ba"` handled automatically by the script; if ffprobe reports no audio track, re-download rather than patching the file.

## Limits

- Deleted posts and protected accounts cannot be recovered — media is gone server-side.
- Only download content the user has the right to keep; respect platform terms and copyright.
