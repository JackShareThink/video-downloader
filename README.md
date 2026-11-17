# video-downloader

输入链接即可下载视频的小工具，基于 [yt-dlp](https://github.com/yt-dlp/yt-dlp)。

解决三个实际痛点：自动挑可用代理、优先选带声音的单文件画质（避开 HLS 分片风暴）、下载后自动校验音视频轨道。

## 特点

- **自动代理**：探测缓存 + 系统代理 + 环境变量 + 常见本地端口，找到可用通道后记住它，下次直接用
- **智能选画质**：优先挑带声音的渐进式 MP4；没有则回退到视频 + 音频流并用 ffmpeg 合并
- **断点续传**：中断后重跑同一命令接着下
- **下载后校验**：用 ffprobe 检查时长、分辨率、音视频轨道，缺音轨会告警
- **双入口**：命令行 + Windows 双击 bat 交互

## 依赖

- Python 3.8+
- yt-dlp：`python -m pip install -U yt-dlp`
- ffmpeg / ffprobe（仅合并分离音轨、校验时需要，下载单文件 MP4 不需要）

## 用法

双击 `download_video.bat`，粘贴链接回车即可。命令行：

```bash
python video_downloader.py                       # 交互模式，提示输入链接
python video_downloader.py <url>                 # 按最高画质下载
python video_downloader.py <url> --quality 720   # 限制最高 720p
python video_downloader.py <url> --audio         # 只保存 MP3
python video_downloader.py <url> --list          # 只看有哪些画质，不下载
python video_downloader.py <url> --cookies edge  # 登录可见内容用浏览器 cookie
python video_downloader.py <url> --proxy http://127.0.0.1:7890  # 手动指定代理
```

默认保存到脚本上一级目录的 `output/`，可用 `--out` 改。下载记录写入 `scripts/downloads.jsonl`，代理缓存写入 `scripts/.proxy_cache.json`（都不含敏感信息）。

## 说明

- 仅用于下载你有权保存的内容，请遵守各平台服务条款和版权规定。
- 私密/需要登录的帖子请用 `--cookies` 提供你自己的会话；工具不会保存或上传 cookie。
- 平台改版导致解析失败时，先升级 yt-dlp：`python -m pip install -U yt-dlp`。

## License

MIT
