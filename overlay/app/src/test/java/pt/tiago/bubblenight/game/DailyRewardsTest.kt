package pt.tiago.bubblenight.game

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class DailyRewardsTest {

    private val today = LocalDate.of(2026, 11, 5)
    private val yesterday = today.minusDays(1)

    @Test fun firstClaimGivesDayOneAndStartsTheStreak() {
        val claimed = DailyRewards.claim(DailyState(), today)
        assertEquals(1, claimed.streak)
        assertEquals(DailyRewards.table[0].coins.toLong(), claimed.coins)
        assertEquals(today.toString(), claimed.lastClaimIso)
    }

    @Test fun claimingTwiceOnTheSameDayChangesNothing() {
        val once = DailyRewards.claim(DailyState(), today)
        val twice = DailyRewards.claim(once, today)
        assertEquals(once, twice)
        assertFalse(DailyRewards.canClaim(once, today))
    }

    @Test fun consecutiveDaysAdvanceTheStreak() {
        var state = DailyRewards.claim(DailyState(), today.minusDays(2))
        state = DailyRewards.claim(state, yesterday)
        state = DailyRewards.claim(state, today)
        assertEquals(3, state.streak)
        assertEquals(3, state.bestStreak)
    }

    @Test fun aMissedDayResetsToDayOneNotZero() {
        val stale = DailyState(lastClaimIso = today.minusDays(5).toString(), streak = 6, bestStreak = 6)
        val claimed = DailyRewards.claim(stale, today)
        assertEquals(1, claimed.streak)
        assertEquals(6, claimed.bestStreak)
    }

    @Test fun theCycleWrapsInsteadOfDroppingBackToDayOne() {
        assertEquals(0, DailyRewards.dayIndex(1))
        assertEquals(6, DailyRewards.dayIndex(7))
        assertEquals(6, DailyRewards.dayIndex(14))
        assertEquals(0, DailyRewards.dayIndex(8))
        assertEquals(0, DailyRewards.dayIndex(0))
        assertEquals(DailyRewards.dayIndex(7), DailyRewards.dayIndex(21))
    }

    @Test fun daySevenPaysTheMost() {
        val jackpot = DailyRewards.table.maxByOrNull { it.coins }!!
        assertEquals(7, jackpot.day)
        assertNotNull(jackpot.booster)
    }

    @Test fun everyCycleDayHasAnEntry() {
        assertEquals(DailyRewards.CYCLE, DailyRewards.table.size)
        assertEquals((1..DailyRewards.CYCLE).toList(), DailyRewards.table.map { it.day })
    }

    @Test fun boostGrowsWithTheStreakAndIsCappedAtDouble() {
        assertEquals(1f, DailyRewards.boostFor(0).multiplier, 1e-4f)
        assertEquals(1.25f, DailyRewards.boostFor(1).multiplier, 1e-4f)
        assertEquals(1.5f, DailyRewards.boostFor(3).multiplier, 1e-4f)
        assertEquals(2f, DailyRewards.boostFor(7).multiplier, 1e-4f)
        assertEquals(2f, DailyRewards.boostFor(30).multiplier, 1e-4f)
    }

    @Test fun aClaimArmsTheBoostAndRunsSpendIt() {
        var state = DailyRewards.claim(DailyState(), today)
        assertTrue(state.boostRunsLeft > 0)
        val runs = state.boostRunsLeft
        repeat(runs) { state = DailyRewards.consumeBoostRun(state) }
        assertEquals(0, state.boostRunsLeft)
        assertEquals(1f, state.boostMultiplier, 1e-4f)
        assertEquals(state, DailyRewards.consumeBoostRun(state))
    }

    @Test fun boostOnlyAppliesWhileRunsRemain() {
        val armed = DailyState(boostRunsLeft = 2, boostMultiplier = 2f)
        assertEquals(200L, DailyRewards.applyBoost(100L, armed))
        assertEquals(100L, DailyRewards.applyBoost(100L, DailyState()))
    }

    @Test fun aCorruptDateIsTreatedAsNeverClaimed() {
        val corrupt = DailyState(lastClaimIso = "not-a-date", streak = 4)
        assertTrue(DailyRewards.canClaim(corrupt, today))
        assertEquals(1, DailyRewards.streakIfClaimed(corrupt, today))
    }

    @Test fun clockRollbackDoesNotGrantAFreeExtraDay() {
        val future = DailyState(lastClaimIso = today.plusDays(1).toString(), streak = 3)
        assertFalse(DailyRewards.canClaim(future, today))
        assertEquals(3, DailyRewards.streakIfClaimed(future, today))
    }

    @Test fun upcomingRewardPreviewsWhatClaimingWouldGive() {
        val state = DailyState(lastClaimIso = yesterday.toString(), streak = 2)
        val upcoming = DailyRewards.upcomingReward(state, today)
        assertEquals(DailyRewards.table[2], upcoming)
        assertNull(DailyRewards.table[0].booster)
    }
}
