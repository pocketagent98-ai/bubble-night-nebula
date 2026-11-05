"""Edit anchors for the Nebula overlay.

Kept as a Python module rather than JSON so the multi-line anchors can be
written literally, with no escaping to get wrong.

Each `old` must occur exactly once in the upstream file; `apply_overlay.py`
checks that before it writes anything.
"""

BASE_REPOSITORY = 'https://github.com/SyscallBrain/bubble-night'
BASE_COMMIT = 'b08ed1eb0d2aa7c9aa4a57878fd1a935886ac22b'

NEW_FILES = [
    'app/src/main/java/pt/tiago/bubblenight/nebula/NebulaMath.kt',
    'app/src/main/java/pt/tiago/bubblenight/nebula/NebulaMapScreen.kt',
    'app/src/main/java/pt/tiago/bubblenight/game/Boosters.kt',
    'app/src/main/java/pt/tiago/bubblenight/game/DailyRewards.kt',
    'app/src/main/java/pt/tiago/bubblenight/game/AudioController.kt',
    'app/src/main/java/pt/tiago/bubblenight/data/RewardStore.kt',
    'app/src/test/java/pt/tiago/bubblenight/nebula/NebulaMathTest.kt',
    'app/src/test/java/pt/tiago/bubblenight/game/DailyRewardsTest.kt',
    'app/src/test/java/pt/tiago/bubblenight/game/BoostersTest.kt',
    'tools/dsp.py',
    'tools/gen_audio.py',
    'tools/gen_sprites.py',
    'tools/verify_build.py',
    'tools/research_probe.py',
    'docs/RESEARCH.md',
    'docs/UPGRADE.md',
    'docs/reference_snapshot.json',
    'notebooks/BubbleNight_Nebula_Studio.ipynb',
]

EDITS = [
    {
        "path": 'app/src/main/java/pt/tiago/bubblenight/ui/UiModels.kt',
        "old": """    START, MAP, PREPARATION, GAME, FREE_MODE_SELECT, FREE_GAME, SETTINGS, STATISTICS, CREDITS, PAUSED, WON, LOST, DAILY, ZEN_SELECT,""",
        "new": """    START, MAP, PREPARATION, GAME, FREE_MODE_SELECT, FREE_GAME, SETTINGS, STATISTICS, CREDITS, PAUSED, WON, LOST, DAILY, ZEN_SELECT,
    /** 3D constellation map with the daily reward and booster tray. */
    NEBULA,""",
    },
    {
        "path": 'app/src/main/java/pt/tiago/bubblenight/ui/UiModels.kt',
        "old": """    fun onOpenMap() {}""",
        "new": """    fun onOpenMap() {}
    fun onOpenNebula() {}""",
    },
    {
        "path": 'app/src/main/java/pt/tiago/bubblenight/ui/BubbleNightApp.kt',
        "old": """import androidx.compose.ui.unit.sp""",
        "new": """import androidx.compose.ui.unit.sp
import pt.tiago.bubblenight.nebula.NebulaMapScreen""",
    },
    {
        "path": 'app/src/main/java/pt/tiago/bubblenight/ui/BubbleNightApp.kt',
        "old": """                    UiScreen.MAP -> MapPage(model, callbacks, pageModifier)""",
        "new": """                    UiScreen.MAP -> MapPage(model, callbacks, pageModifier)
                    UiScreen.NEBULA -> NebulaMapScreen(model, callbacks, pageModifier)""",
    },
    {
        "path": 'app/src/main/java/pt/tiago/bubblenight/ui/BubbleNightApp.kt',
        "old": """        MenuRow(stringResource(R.string.menu_free), stringResource(R.string.menu_free_sub), "\u25c9", callbacks::onOpenFreeGame)""",
        "new": """        MenuRow("Nebula map", "3D constellation, boosters and daily rewards", "\u2726", callbacks::onOpenNebula)
        MenuRow(stringResource(R.string.menu_free), stringResource(R.string.menu_free_sub), "\u25c9", callbacks::onOpenFreeGame)""",
    },
    {
        "path": 'app/src/main/java/pt/tiago/bubblenight/game/GameViewModel.kt',
        "old": """    override fun onOpenMap() {
        if (!loaded || busy) return
        animationEvents = emptyList(); audio.setActive(false)
        selectedOrbit = orbitNumber(catalog!!.levels.first { it.id == selectedId })
        screen = UiScreen.MAP; render()
    }""",
        "new": """    override fun onOpenMap() {
        if (!loaded || busy) return
        animationEvents = emptyList(); audio.setActive(false)
        selectedOrbit = orbitNumber(catalog!!.levels.first { it.id == selectedId })
        screen = UiScreen.MAP; render()
    }

    /** Nebula map: the same orbit as the flat map, drawn in 3D, plus the daily layer. */
    override fun onOpenNebula() {
        if (!loaded || busy) return
        animationEvents = emptyList(); audio.setActive(false)
        selectedOrbit = orbitNumber(catalog!!.levels.first { it.id == selectedId })
        screen = UiScreen.NEBULA; render()
    }""",
    },
]
