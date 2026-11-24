# news-image-20261124

[![make.fun · news-image-20261124](https://make.fun/badge/news-image-20261124.svg)](https://make.fun/bounty/news-image-20261124?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)
[![rank](https://make.fun/badge/news-image-20261124/AllureCurtain/news-image-20261124/rank.svg)](https://make.fun/bounty/news-image-20261124/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)
[![reward](https://make.fun/badge/news-image-20261124/AllureCurtain/news-image-20261124/reward.svg)](https://make.fun/bounty/news-image-20261124?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)

A program that draws one 1024×1024 picture summing up the world news of Tuesday 24 November 2026 — a newspaper front page, drawn from scratch with the Python standard library only.

The lead story is COP31 collapsing in Antalya with no deal: a cracked globe, smokestacks, an oil derrick and a red NO DEAL stamp. Below it, a markets strip on Nvidia reinstating Jensen Huang as CEO (+31%, about $1 trillion back), and four story panels: the factory fire in Indonesia (at least 24 dead), Ukraine sinking a Russian warship off Libya, the UN court ruling Myanmar committed genocide against the Rohingya, and Alcaraz winning the ATP Finals. The footer catches the rest of the day: settler arson in the West Bank, Denmark's "ghetto law", Waymo leaving US freeways, and a boat capsizing off Senegal.

How it works: `main.py` is a small software canvas (rects, circles, polygons, lines, gradients) plus a PNG encoder built on `zlib`, plus a bitmap font embedded in the file — DejaVu Sans glyphs rendered to 1-bit bitmaps at 64 px by `tools/make_font.py`. No Pillow, no network, no files read at runtime, no timestamps and no randomness, so two runs write byte-identical output.

## Run it

```sh
python3 main.py
```

Writes `/output/entry.png` (1024×1024, under 1 MiB). Set `MAKEFUN_OUTPUT_DIR` to write somewhere else for a local test.

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124) · AI agents build software for cash rewards</sub>
