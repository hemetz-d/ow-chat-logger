# GUI screenshots

Images referenced from the top-level [README.md](../../README.md). Drop new
captures here using the filenames listed below.

## Naming convention

| File | Tab / state to capture |
|---|---|
| `live-feed.png` | Live Feed tab with several recent rows visible. Include at least one Team, one All-chat, and one Hero row so the channel-color dots are all represented. A row with the "NEW" badge visible is a plus. |
| `search.png` | Search tab with a query entered (~3+ chars), inline match highlights visible, and at least the Channel + Time-window filter rail on the right. |

Optional / nice to have:

| File | Tab / state to capture |
|---|---|
| `settings.png` | Settings tab with the capture-interval segmented control + accent picker visible. |
| `onboarding.png` | Live Feed tab on a fresh install — empty state with the Configuration side panel and Tip card. |
| `player-history.png` | Live Feed with the player side panel open after clicking a player name. |

## Capture tips

- Use the **Dark** appearance mode for consistency with the existing accent
  palette presentation. Light mode shots are welcome as a separate set
  (`*-light.png`) but Dark is the canonical one for the README.
- Window size **960×660** (the app's launch geometry). Avoid screenshots of a
  resized / maximized window — the side panels reflow at extreme sizes and
  don't represent the typical layout.
- Crop tightly to the window (no desktop background, no taskbar).
- Save as PNG (avoid JPEG — chrome compression artefacts on UI text are
  distracting).
- Target ≤ 600 KB per image. Use `pngcrush` or similar if needed; a 960-wide
  PNG of the GUI compresses comfortably under that.
- Do **not** include real player names from a recorded session in the
  screenshots intended for the public README. Either use a development DB
  seeded with synthetic names, or blur the player column.
