# EXPLOSION!!!

A pygame magic explosion effect demo inspired by the "explosion magic" spell archetype.

## Demo

A 15-second scripted sequence plays automatically:

| Time | Phase |
|------|-------|
| 0–4.5s | Chant — rotating magic circle expands, sparkles appear, purple energy converges |
| 4.5–5.2s | Cast — magic circle spins up, lightning discharges |
| 5.2–5.5s | Detonation — flash, fireball, shockwave rings, debris, lava droplets |
| 5.5–6.5s | Peak — rays, ground cracks, smoke |
| 6.5–9.5s | Sustained burn — fire wisps rise, ember particles |
| 9.5–15s | Fade out |

## Requirements

- Python 3.12+
- pygame 2.6+
- numpy 2.4+ (optional — enables procedural audio)

## Setup

```bash
uv sync
```

## Run

```bash
uv run main.py
```

## Controls

| Key | Action |
|-----|--------|
| `R` | Restart |
| `P` | Pause / Resume |
| `ESC` | Quit |

## Effects

- Rotating 7-pointed-star magic circle with hex inner ring
- Cross-shaped sparkles with spin animation
- Recursive zigzag lightning bolts
- Radial gradient fireball (9-stop color interpolation)
- 4 concentric shockwave rings
- 500 fire sparks + 250 ember particles + 80 purple mana fragments
- 100 rotating debris polygons (rock/metal) with ground bounce
- 80 lava droplets that pool on landing
- Fire wisps with sinusoidal path and trail rendering
- Screen shake (90 frames, exponential decay)
- Procedural audio via numpy: hum, charge sweep, sub-bass explosion, crackle loop

## macOS Note

`pygame.font.SysFont` crashes when font paths contain spaces. This project uses
`pygame.font.Font` with absolute paths to Hiragino Gothic instead.
