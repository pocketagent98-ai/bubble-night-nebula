# Reference research: what the three listings actually say

This document is the output of `tools/research_probe.py`, run against the three
store pages you supplied. The probe reads the live listing, extracts capability
signals with a keyword map and writes `docs/research_snapshot.json`. On
2026-11-05 all three fetches were live (see `liveFetches: 3` in that file).

Nothing below is a guess about how those games work internally — it is what
their store text claims, plus what the ratings say, plus the design decision
taken for this build.

## The three references

| | Bubble Shooter | Bubble Pop: Ball Shooter | Bubble Shooter — Classic Pop |
|---|---|---|---|
| Developer | Happy Dragon Inc. | HDuo Fun Games | Ilyon Dynamics Ltd. |
| Rating | 4.5 | 4.9 | 4.6 |
| Reviews | 1.14M | 69.5K | 2.36M |
| Installs | 100M+ | 10M+ | 500M+ |
| Model | Ads | Ads | Ads + IAP |

## Capability matrix

`●` present in the listing · `·` absent

| Capability | Dragon | HDuo | Ilyon | Taken into Nebula |
|---|:--:|:--:|:--:|---|
| Tap to swap the loaded bubble | · | ● | · | already in Bubble Night (`onSwap`) |
| Drag/laser aim | ● | ● | ● | kept, plus the existing bounce preview |
| Match 3+ | ● | ● | ● | core rule, unchanged |
| Combo chain scoring | · | ● | ● | new: rising pop ladder + chain sting |
| Fireball booster | · | ● | ● | new: `BoosterId.FIREBALL`, unlocks after a 7-chain |
| Bomb booster | · | · | ● | new: `BoosterId.BOMB`, unlocks after a 10-drop |
| Other boosters / props | ● | ● | ● | new: 10 boosters with shot cooldowns |
| Daily reward | · | · | ● | new: 7-day wrapping cycle + streak boost |
| Coins economy | · | · | ● | new: coins are earned only, never sold |
| Colour-blind mode | · | · | ● | kept (symbols), plus generated symbol sprites |
| Episode / map adventure | · | ● | · | new: 3D nebula map |
| Characters / pets | ● | ● | · | not taken — Bubble Night stays a night-sky game |
| Leaderboard | · | · | ● | not taken — needs a server, and the game is offline |
| Obstacles (rocks) | · | · | ● | already in Bubble Night (`ROCK`) |
| Offline, no wifi | ● | ● | ● | kept, and enforced: no network permission |
| Music / effects | ● | ● | ● | new: 29 synthesised cues |

## What each one is actually good at

**Happy Dragon's Bubble Shooter** wins on volume and clarity: 100M installs from
a plain "aim, match three, collect stars" loop with a single mascot. Its listing
barely mentions anything else. The lesson is that the *core* has to be instantly
legible; everything else is decoration.

**HDuo's Bubble Pop** is the one that cares about feel. "Smooth animation and
interesting music keep you immersed", "consecutively breaking balls can add
points", "beat levels to unlock new episodes". Its 4.9 rating over 69.5K reviews
is the highest of the three, on the smallest install base. The lesson: the
moment-to-moment feedback loop — chain scoring, animation, episode progress —
is what people rate, not the level count.

**Ilyon's Classic Pop** is the systems game. Daily rewards, coins, boosters,
colour-blind mode, two modes, leaderboard, achievements, 3000+ levels. Two
specific mechanics are worth copying verbatim because they are *earned* rather
than bought: **pop 7 in a row to unlock the fireball** and **drop 10+ at once to
get a bomb**. The lesson: tie the powerful toy to skilful play, not to a shop.

## What was deliberately rejected

All three are ad-supported, and Ilyon also sells in-app purchases. The reviews on
the Happy Dragon listing complain specifically that an ad appears when a level is
almost finished and blocks play. Bubble Night's whole premise is an offline game
with no ads, no accounts and no analytics, and this upgrade keeps that: coins are
earned, boosters unlock by playing, and there is still no network permission in
the manifest. The daily layer is local-calendar only.

## How the research became code

| Finding | Where it landed |
|---|---|
| Earned, not bought, boosters | `game/Boosters.kt` — every booster has an unlock condition tied to orbit or streak |
| Fireball at 7-chain, bomb at 10-drop | `BoosterId.FIREBALL` / `BOMB` unlock rules and cooldowns |
| Daily reward must not reset to day 1 | `game/DailyRewards.kt` — the 7-day cycle wraps, and a missed day resets to 1, not 0 |
| Chain scoring is what gets rated | `AudioController` pop ladder (5 rungs) + `chainN` stings |
| Episodes need a map | `nebula/NebulaMapScreen.kt` — 3D constellation path per orbit |
| Colour-blind mode | existing symbol setting, now backed by generated symbol sprites |
| Ads are the top complaint | nothing to reject: the build still has no ad code and no INTERNET permission |
