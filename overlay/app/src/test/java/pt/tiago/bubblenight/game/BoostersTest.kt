package pt.tiago.bubblenight.game

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BoostersTest {

    @Test fun theCatalogueHasTenDistinctBoosters() {
        assertEquals(10, Boosters.all.size)
        assertEquals(Boosters.all.size, Boosters.all.map { it.id }.distinct().size)
        assertEquals(Boosters.all.size, Boosters.all.map { it.label }.distinct().size)
    }

    @Test fun everyBoosterNamesAGeneratedSound() {
        val generated = setOf(
            "fireball", "bomb", "rocket", "lightning", "freeze", "shield",
            "rainbow", "whoosh", "levelup", "star", "coin", "daily", "booster",
        )
        for (spec in Boosters.all) {
            assertTrue("${spec.id} uses ${spec.sound}", spec.sound in generated)
        }
    }

    @Test fun theFireballIsTheOnlyStarterBooster() {
        val unlocked = Boosters.unlockedAt(orbit = 1, streak = 0)
        assertEquals(setOf(BoosterId.FIREBALL), unlocked)
    }

    @Test fun unlocksFollowOrbitAndStreak() {
        assertTrue(BoosterId.BOMB in Boosters.unlockedAt(orbit = 2, streak = 0))
        assertFalse(BoosterId.BOMB in Boosters.unlockedAt(orbit = 1, streak = 0))
        assertTrue(BoosterId.LIGHTNING in Boosters.unlockedAt(orbit = 4, streak = 0))
        assertFalse(BoosterId.SHUFFLE in Boosters.unlockedAt(orbit = 8, streak = 0))
        assertTrue(BoosterId.SHUFFLE in Boosters.unlockedAt(orbit = 9, streak = 0))
        assertFalse(BoosterId.RAINBOW in Boosters.unlockedAt(orbit = 12, streak = 2))
        assertTrue(BoosterId.RAINBOW in Boosters.unlockedAt(orbit = 1, streak = 3))
        assertTrue(BoosterId.TIMEWARP in Boosters.unlockedAt(orbit = 1, streak = 7))
    }

    @Test fun unlockingIsMonotonicInOrbit() {
        var previous = 0
        for (orbit in 1..12) {
            val count = Boosters.unlockedAt(orbit, streak = 0).size
            assertTrue("orbit $orbit regressed", count >= previous)
            previous = count
        }
        assertEquals(Boosters.all.size, Boosters.unlockedAt(12, streak = 7).size)
    }

    @Test fun cooldownReArmsExactlyAtTheThreshold() {
        val bomb = Boosters.byId(BoosterId.BOMB)
        assertFalse(Boosters.isReady(bomb, bomb.cooldownShots - 1))
        assertTrue(Boosters.isReady(bomb, bomb.cooldownShots))
        assertTrue(Boosters.isReady(bomb, bomb.cooldownShots + 5))
    }

    @Test fun cooldownFractionIsClamped() {
        val bomb = Boosters.byId(BoosterId.BOMB)
        assertEquals(0f, Boosters.cooldownFraction(bomb, 0), 1e-4f)
        assertEquals(1f, Boosters.cooldownFraction(bomb, bomb.cooldownShots * 3), 1e-4f)
        val half = Boosters.cooldownFraction(bomb, bomb.cooldownShots / 2)
        assertTrue(half in 0.4f..0.6f)
    }

    @Test fun everyBoosterHasAPositiveCooldownAndAGlyph() {
        for (spec in Boosters.all) {
            assertTrue("${spec.id} cooldown", spec.cooldownShots > 0)
            assertTrue("${spec.id} glyph", spec.glyph.isNotEmpty())
            assertTrue("${spec.id} description", spec.description.length > 20)
        }
    }
}
