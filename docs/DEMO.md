# Demo

The README references an animated walkthrough at [`docs/demo.gif`](demo.gif).
This document contains the **storyboard** for that GIF and instructions for
generating it. Record the GIF, save it as `docs/demo.gif`, and it will appear in
the README automatically.

## Storyboard (≈ 30 seconds)

| Scene | Duration | What to show |
|-------|----------|--------------|
| 1 | 2s | Run `pytest` in the terminal |
| 2 | 2s | A test **fails** (red output) |
| 3 | 4s | Evidence collection — screenshot, console, network, logs, DOM |
| 4 | 2s | **AI Failure Analysis** starts |
| 5 | 3s | **Root cause** generated |
| 6 | 2s | **Confidence score** displayed |
| 7 | 3s | **Bug report** generated |
| 8 | 3s | **HTML report** opens |
| 9 | 2s | Run `python qa_ai.py analyze-last-failure` |
| 10 | 3s | Interactive AI response |
| 11 | 2s | Framework summary |

## How to record

Pick any tool:

- **[ScreenToGif](https://www.screentogif.com/)** (Windows, recommended) — record a
  screen region, edit frames, and export directly to GIF.
- **[Peek](https://github.com/phw/peek)** (Linux) — lightweight region-to-GIF recorder.
- **[OBS Studio](https://obsproject.com/)** — record to MP4, then convert (see below).
- **[asciinema](https://asciinema.org/)** — for terminal-only, text-based casts
  (`asciinema rec demo.cast`), optionally converted to GIF with
  [`agg`](https://github.com/asciinema/agg).

### Convert MP4 → optimized GIF with ffmpeg

```bash
ffmpeg -i demo.mp4 -vf "fps=12,scale=1000:-1:flags=lanczos,palettegen" palette.png
ffmpeg -i demo.mp4 -i palette.png -vf "fps=12,scale=1000:-1:flags=lanczos,paletteuse" docs/demo.gif
```

## GIF requirements

- **Under 30 seconds**
- **Under 15 MB** (GitHub renders inline up to this size comfortably)
- **Optimized for GitHub** — 10–12 fps, ~1000px wide, palette-based colors

> Tip: run `gifsicle -O3 --colors 128 docs/demo.gif -o docs/demo.gif` to shrink further.
