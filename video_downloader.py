#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""输入链接直接下载视频：自动选代理、自动挑带声音的最高画质、断点续传、下载后校验。

用法：
    python video_downloader.py                      # 交互模式，提示输入链接
    python video_downloader.py <url>                # 直接下载
    python video_downloader.py <url> --quality 720  # 限制最高 720p
    python video_downloader.py <url> --audio        # 只存 MP3
    python video_downloader.py <url> --list         # 只看有哪些画质，不下载
    python video_downloader.py <url> --proxy http://127.0.0.1:3067
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
CACHE_FILE = BASE / ".proxy_cache.json"
DEFAULT_OUT = BASE.parent / "output"
HISTORY_FILE = BASE / "downloads.jsonl"
COMMON_PROXY_PORTS = [3067, 7890, 7897, 10809, 1080, 8889, 2080]
DIRECT = "__direct__"
DEFAULT_NAME = "%(uploader)s-%(id)s.%(ext)s"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def log(msg):
    print(msg, flush=True)


def ytdlp_cmd():
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        subprocess.run([sys.executable, "-m", "yt_dlp", "--version"],
                       capture_output=True, check=True, timeout=30)
        return [sys.executable, "-m", "yt_dlp"]
    except Exception:
        sys.exit("错误：没找到 yt-dlp。安装命令：python -m pip install -U yt-dlp")


def load_cache():
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(host, proxy):
    data = load_cache()
    data[host] = proxy or DIRECT
    try:
        CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def windows_system_proxy():
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        server, _ = winreg.QueryValueEx(key, "ProxyServer")
        if enable and server:
            if "=" in server:
                for part in server.split(";"):
                    if part.lower().startswith("https="):
                        return "http://" + part.split("=", 1)[1]
            return "http://" + server
    except Exception:
        pass
    return None


def reachable(proxy, host):
    handlers = []
    if proxy and proxy != DIRECT:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(
        "https://%s/robots.txt" % host, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with opener.open(req, timeout=8) as resp:
            return resp.status < 500
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def resolve_proxy(mode, host):
    if mode == "none":
        return None
    if mode not in ("auto", None):
        candidates = [mode]
    else:
        cached = load_cache().get(host)
        if cached == DIRECT:
            cached = None
        env = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        candidates = [cached, env, windows_system_proxy()]
        candidates += ["http://127.0.0.1:%d" % p for p in COMMON_PROXY_PORTS]
        candidates.append(None)

    seen = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        if reachable(cand, host):
            save_cache(host, cand)
            log("[代理] %s" % (cand or "直连"))
            return cand
    log("[代理] 没找到可用通道，尝试直连")
    return None


def base_args(proxy, cookies):
    args = ytdlp_cmd() + ["--no-update", "--no-colors"]
    if proxy:
        args += ["--proxy", proxy]
    if cookies:
        args += ["--cookies-from-browser", cookies]
    return args


def fetch_info(url, args):
    proc = subprocess.run(
        args + ["-J", "--skip-download", url],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        sys.stderr.write((proc.stderr or "")[-2000:] + "\n")
        sys.exit("错误：读取视频信息失败（详见上方报错）")
    try:
        return json.loads(proc.stdout)
    except Exception:
        sys.exit("错误：视频信息解析失败")


def is_muxed(fmt):
    """X 的渐进式 http-* 流把编解码器标成 None，但有画面即视为带声音单文件。"""
    if not fmt.get("height"):
        return False
    v, a = fmt.get("vcodec"), fmt.get("acodec")
    if v == "none":
        return False
    if v and a and a != "none":
        return True
    if v is None and a is None:
        return str(fmt.get("protocol", "")).startswith("http")
    return False


def pick_formats(info, ceiling):
    formats = info.get("formats") or []
    prog = [f for f in formats if is_muxed(f)]
    if prog:
        pool = [f for f in prog if f["height"] <= ceiling] if ceiling else prog
        pool = pool or prog
        best = max(pool, key=lambda f: (f["height"], f.get("tbr") or 0))
        return best["format_id"], "渐进式 %dp（单文件含声音）" % best["height"]

    vids = [f for f in formats
            if f.get("vcodec") not in (None, "none") and f.get("height")]
    auds = [f for f in formats
            if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")]
    if ceiling and vids:
        fit = [f for f in vids if f["height"] <= ceiling]
        vids = fit or vids
    if not vids:
        return "best", "默认最佳"
    v = max(vids, key=lambda f: (f["height"], f.get("tbr") or 0))
    if auds:
        a = max(auds, key=lambda f: f.get("abr") or 0)
        return "%s+%s" % (v["format_id"], a["format_id"]), \
               "%dp + 独立音轨（需 ffmpeg 合并）" % v["height"]
    return v["format_id"], "%dp（无音轨）" % v["height"]


def print_formats(info):
    def row(*cells):
        return ("  ".join(str(c) for c in cells)).rstrip()
    log(row("ID", "EXT", "RES", "VCODEC", "ACODEC"))
    log("-" * 68)
    for f in info.get("formats") or []:
        res = "%sx%s" % (f.get("width"), f.get("height")) if f.get("height") else "audio only"
        log(row(f["format_id"], f.get("ext", ""), res,
                f.get("vcodec") or "-", f.get("acodec") or "-"))


def verify(path):
    if not os.path.exists(path):
        return "校验失败：文件不存在"
    if not shutil.which("ffprobe"):
        return "未安装 ffprobe，跳过校验"
    proc = subprocess.run(
        ["ffprobe", "-v", "error",
         "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height",
         "-of", "default=noprint_wrappers=1", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in (proc.stdout or "").splitlines() if l.strip()]
    if not lines:
        return "校验失败：无法读取媒体信息"
    return " | ".join(lines)


def record_history(url, path, info, selector):
    try:
        with HISTORY_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "time": datetime.now().isoformat(timespec="seconds"),
                "url": url,
                "file": str(path),
                "title": info.get("title"),
                "duration": info.get("duration"),
                "format": selector,
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description="输入链接下载视频（自动代理 / 自动选画质）")
    ap.add_argument("url", nargs="?", help="视频链接；不填则进入交互模式")
    ap.add_argument("--quality", default="best", help="best|2160|1440|1080|720|480|360")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="保存目录")
    ap.add_argument("--audio", action="store_true", help="只提取 MP3")
    ap.add_argument("--list", action="store_true", help="只列出画质，不下载")
    ap.add_argument("--cookies", help="浏览器 cookie：edge|firefox|chrome|brave")
    ap.add_argument("--proxy", default="auto", help="auto|<url>|none")
    ap.add_argument("--name", default=DEFAULT_NAME, help="文件名模板")
    a = ap.parse_args()

    url = (a.url or "").strip()
    if not url:
        try:
            url = input("请输入视频链接（直接回车退出）: ").strip()
        except (EOFError, KeyboardInterrupt):
            log("\n已取消")
            return
    if not url:
        log("没有输入链接，退出")
        return

    host = urllib.parse.urlparse(url).hostname or "x.com"
    proxy = resolve_proxy(a.proxy, host)
    args = base_args(proxy, a.cookies)

    log("[信息] 正在读取视频信息...")
    info = fetch_info(url, args)
    log("[信息] %s | %s | %s" % (
        info.get("uploader") or "?", info.get("duration_string") or "?",
        (info.get("title") or "")[:70]))

    ceiling = None if a.quality == "best" else int(a.quality)
    if a.list:
        print_formats(info)
        sel, desc = pick_formats(info, ceiling)
        log("\n[推荐] %s  (%s)" % (sel, desc))
        return

    name_tpl = a.name
    if a.audio:
        selector, desc = "ba/b", "仅音频 -> MP3"
        extra = ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
        # 音频单独命名，防止 yt-dlp 把已有同名视频当成源文件并删掉它。
        # 中间 mp4 由 yt-dlp 转完 mp3 后自动清理，不用 --keep-video。
        if name_tpl == DEFAULT_NAME:
            name_tpl = "%(uploader)s-%(id)s-audio.%(ext)s"
    else:
        selector, desc = pick_formats(info, ceiling)
        extra = ["--merge-output-format", "mp4"] if "+" in selector else []

    out_dir = Path(a.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    log("[画质] %s  (%s)" % (selector, desc))
    log("[保存] %s" % out_dir)

    cmd = args + ["-f", selector] + extra + [
        "--continue", "--retries", "30", "--fragment-retries", "30", "-N", "4",
        "-o", str(out_dir / name_tpl), url]
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        sys.exit("错误：下载中断（已下载部分可以重跑本命令续传）")

    ext = "mp3" if a.audio else "mp4"
    name = (name_tpl.replace("%(uploader)s", str(info.get("uploader") or "video"))
            .replace("%(id)s", str(info.get("id") or ""))
            .replace("%(title)s", (info.get("title") or "video")[:80])
            .replace("%(ext)s", ext))
    final = out_dir / name
    log("\n完成：%s" % final)
    log("[校验] %s" % verify(str(final)))
    record_history(url, final, info, selector)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n已取消")
