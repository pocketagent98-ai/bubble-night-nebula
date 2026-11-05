# What the Nebula upgrade adds, A to Z

A map of every change, so you can find things. Files marked *(new)* did not exist
before; everything else is an edit to an existing file.

## A — Audio

`game/AudioController.kt` *(rewritten)* now carries 20 named cues instead of 6.
The important behavioural change is the **pop ladder**: a match no longer replays
one sample. Five rising pops (`pop1`–`pop5`) are chosen by how quickly matches
land, and at a chain of 3 or more a `chainN` sting joins in. A chain therefore
sounds like a melody climbing, which is the single biggest "juice" upgrade in
this build.

All 29 samples are synthesised by `tools/gen_audio.py` from oscillators and
filtered noise. No third-party audio, no licence file to ship, 1.4 MB total,
regenerated in under 2 seconds.

## B — Boosters

`game/Boosters.kt` *(new)*. Ten boosters, each with a glyph, a cue, a cooldown in
shots, a clear radius and an unlock rule:

`FIREBALL` · `BOMB` · `ROCKET` · `LIGHTNING` · `FREEZE` · `SHIELD` · `RAINBOW` ·
`MAGNET` · `SHUFFLE` · `TIMEWARP`

Nothing is purchasable. Unlocks come from orbit progress or daily streak, which
is the "earned, not sold" reading of what the reference games do.

## C — Camera

`nebula/NebulaMath.kt` *(new)* is a small pinhole camera: yaw, pitch, distance,
focal length, near-plane culling, distance fog and an explicit xorshift star
field. It is pure Kotlin with no Android types, so all of it is unit-tested.

## D — Daily reward

`game/DailyRewards.kt` *(new)* and `data/RewardStore.kt` *(new)*.

The reward is a seven-day cycle that **wraps**: a 14-day streak still pays the day
7 jackpot rather than dropping back to 25 coins. A missed day resets the streak to
1, never to 0, so the first tap after a gap still feels like a win. The streak also
grants a **boost** — a score multiplier for the next few runs — because a
multiplier changes how the game plays and coins do not.

The streak lives in its own `SharedPreferences` file, not in `Profile`. Putting it
in the profile would have forced a schema migration on a format that ships with
checksums, backups and a recovery copy; if this file is corrupt the game forgets a
streak and nothing else.

## E — Effects

`nebula/NebulaMapScreen.kt` draws the map entirely from vectors: three drifting
nebula clouds, a 150-star parallax field with per-star twinkle, a glowing
constellation thread with depth beads, and a tap pulse that throws six sparks.

## F — Frame clock

One `withFrameNanos` loop drives the twinkle, the camera drift and the pulse.
Nothing is scheduled per element, so the cost does not grow with the node count.
`reducedMotion` stops the clock entirely rather than slowing it down.

## G — Generated assets

`tools/gen_sprites.py` renders real spheres, not flat discs: per-pixel surface
normals, a Blinn-Phong specular lobe, a Fresnel rim and a transmitted-light
crescent at the bottom. That last one is what separates "3D glass" from "a
coloured circle with a white dot on it".

Outputs: 13 bubbles (6 colours + 6 symbol variants + specials), 7 special bubbles
(rock, star, bomb, fireball, rainbow, ice, shield), 12 orbit planets and 4
particles. About 25 seconds on one core.

## H — Hit testing

`NebulaMath.nearestNode` is a screen-space nearest-hit with a slop factor, and it
reads the *same* projection the renderer used, so what you tap is exactly what you
see. No duplicated geometry maths between drawing and input.

## I — Integration

Three small edits wire the new screen in:

- `ui/UiModels.kt`: `UiScreen.NEBULA` and `onOpenNebula()`.
- `ui/BubbleNightApp.kt`: the `when (model.screen)` branch and a home-screen row.
- `game/GameViewModel.kt`: `onOpenNebula()`, mirroring `onOpenMap()`.

Back navigation already falls through to `onReturnToStart()`, so no extra work.

## J — Journey (the map)

Each orbit's levels are placed on a serpentine path that also moves towards and
away from the viewer, so a flat level list gains real parallax. Drag to rotate the
camera; the map drifts on its own when you do not.

## K — Keeping the save format

No field was added to `Profile`. The campaign, certificates, endless decks and
backup format are untouched, so existing saves keep loading and the 1,800
certified solutions still verify.

## L — Localisation

New strings on the Nebula screen are English literals rather than resources, so
the Portuguese build cannot end up half-translated. The rest of the app still
uses `strings.xml` as before.

## M — Manifest

Unchanged. There is still no `INTERNET` permission. That is the point of the game
and the upgrade does not weaken it.

## N — Notebook

`notebooks/BubbleNight_Nebula_Studio.ipynb` runs the whole pipeline on Colab:
clone, research, generate audio, generate sprites, verify, zip, save to Drive.
One click, about three minutes.

## O — Offline

The research probe is the only step that touches the network, it runs on your
machine (not in the app), and it falls back to `docs/reference_snapshot.json` when
the network is blocked.

## P — Planets

`tools/gen_sprites.py` builds each orbit's planet from domain-warped latitude
bands plus a polar cap, with soft craters stamped as a darkening field on the rocky
orbits. Twelve PNGs, 512 px, about 90 KB each.

## Q — Quality checks

`tools/verify_build.py` runs six checks in a few seconds: bracket balance with a
real Kotlin lexer, `R.raw` references resolving to files, `assets.open` paths
resolving, all JSON parsing, required files present, and every `UiScreen` value
handled by the nav `when`.

## R — Reduced motion

Every animation on the Nebula screen is gated on the existing `reducedMotion`
setting. With it on, the frame clock stops, clouds stop drifting and the planet
ring stops tilting.

## S — Sound bank

29 cues: `launch bounce match drop victory defeat pop1-5 chain1-3 star coin
fireball bomb rocket lightning freeze shield rainbow booster daily levelup
ui_tap whoosh aim`.

## T — Tests

Three new JVM test classes, 31 tests:

- `NebulaMathTest` — projection, culling, determinism, frustum bounds, hit testing, twinkle range.
- `DailyRewardsTest` — first claim, double claim, streak advance, missed day, cycle wrap, boost arming and spending, corrupt date, clock rollback.
- `BoostersTest` — catalogue integrity, sound references, unlock monotonicity, cooldown thresholds.

## U — Unlock rules

`Boosters.unlockedAt(orbit, streak)` is monotonic in orbit, and a test asserts it.

## V — Visual identity

The Nebula layer keeps the Tokyo-Night palette the game already used. The 3D map
is additive: the flat `MapPage` still exists and is still reachable.

## W — Wiring order

`gen_audio.py` and `gen_sprites.py` are independent and can run in parallel;
`verify_build.py` must run after both because it checks their outputs exist.

## X — Extending

To add a booster: add the enum value, one `BoosterSpec`, one cue in
`gen_audio.py`, rerun the generator. The tray and the cooldown ring pick it up
automatically.

## Y — Why no shop

A shop needs a network, a receipt validator and a privacy policy. All three
reference games have ads; the top complaint on the largest one is an ad appearing
at the end of a level. The upgrade spends its complexity budget on feel instead.

## Z — Zero third-party assets

Every byte of art and audio in this upgrade is generated by the two Python
scripts in `tools/`. That means the whole visual and audio layer is reproducible,
diffable and free of licence questions.
