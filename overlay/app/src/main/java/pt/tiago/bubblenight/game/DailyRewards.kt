package pt.tiago.bubblenight.game

import java.time.LocalDate
import java.time.temporal.ChronoUnit

/**
 * Daily reward, daily boost and streak logic.
 *
 * Pure functions over an immutable [DailyState]: the store in
 * `data/RewardStore.kt` only persists the result. That keeps the streak rules
 * unit-testable with fixed dates instead of a mocked clock.
 *
 * Design notes, taken from what the reference games do and where they go wrong:
 *  - A seven-day cycle that *wraps* rather than resetting to day one, so a long
 *    streak keeps paying the good days instead of dropping the player back to
 *    the cheapest reward on day eight.
 *  - Missing a day resets the streak to 1, never to 0, so the first tap after a
 *    gap still feels like a win.
 *  - The streak also grants a *boost* (a score multiplier for a few runs). The
 *    boost is the part that actually changes how the game plays; coins alone do
 *    not.
 */

/** Persisted daily state. Dates are ISO-8601 (`2026-11-05`) for stable sorting. */
data class DailyState(
    val lastClaimIso: String? = null,
    val streak: Int = 0,
    val bestStreak: Int = 0,
    val coins: Long = 0,
    /** Remaining runs of the current boost, and the multiplier attached to them. */
    val boostRunsLeft: Int = 0,
    val boostMultiplier: Float = 1f,
) {
    val claimedToday: Boolean get() = lastClaimIso != null
}

/** One slot of the seven-day cycle. */
data class DailyReward(
    val day: Int,
    val coins: Int,
    val booster: BoosterId?,
    val label: String,
)

/** The score boost a streak buys. */
data class DailyBoost(val multiplier: Float, val runs: Int, val label: String)

object DailyRewards {

    const val CYCLE = 7

    /** The seven slots, in order. Day 7 is the jackpot. */
    val table: List<DailyReward> = listOf(
        DailyReward(1, 25, null, "25 coins"),
        DailyReward(2, 40, BoosterId.FIREBALL, "40 coins + Fireball"),
        DailyReward(3, 60, null, "60 coins + x1.5 boost"),
        DailyReward(4, 90, BoosterId.BOMB, "90 coins + Bomb"),
        DailyReward(5, 130, BoosterId.SHIELD, "130 coins + Shield"),
        DailyReward(6, 180, BoosterId.RAINBOW, "180 coins + Rainbow"),
        DailyReward(7, 300, BoosterId.TIMEWARP, "300 coins + Time Warp + x2"),
    )

    /**
     * Which slot a streak of [streak] days lands on. A streak of 0 (never
     * claimed) previews day 1; a streak of 7 wraps to day 7 and stays there
     * until the streak grows again, which is what makes day 7 repeatable.
     */
    fun dayIndex(streak: Int): Int {
        if (streak <= 0) return 0
        val day = streak % CYCLE
        return if (day == 0) CYCLE - 1 else day - 1
    }

    fun rewardFor(streak: Int): DailyReward = table[dayIndex(streak)]

    /** The slot that will be granted by claiming today. */
    fun upcomingReward(state: DailyState, today: LocalDate): DailyReward =
        rewardFor(streakIfClaimed(state, today))

    /** Streak the player would have after claiming on [today]. */
    fun streakIfClaimed(state: DailyState, today: LocalDate): Int {
        val last = state.lastClaimIso ?: return 1
        val lastDate = runCatching { LocalDate.parse(last) }.getOrNull() ?: return 1
        val gap = ChronoUnit.DAYS.between(lastDate, today)
        return when {
            gap <= 0L -> state.streak.coerceAtLeast(1) // same day, or a clock rollback
            gap == 1L -> state.streak + 1
            else -> 1 // a missed day costs the streak, but never drops to zero
        }
    }

    fun canClaim(state: DailyState, today: LocalDate): Boolean {
        val last = state.lastClaimIso ?: return true
        val lastDate = runCatching { LocalDate.parse(last) }.getOrNull() ?: return true
        return ChronoUnit.DAYS.between(lastDate, today) > 0L
    }

    /**
     * Applies a claim. Returns [state] unchanged when there is nothing to claim,
     * so the caller can treat the result as the new source of truth either way.
     */
    fun claim(state: DailyState, today: LocalDate): DailyState {
        if (!canClaim(state, today)) return state
        val streak = streakIfClaimed(state, today)
        val reward = rewardFor(streak)
        val boost = boostFor(streak)
        return state.copy(
            lastClaimIso = today.toString(),
            streak = streak,
            bestStreak = maxOf(state.bestStreak, streak),
            coins = state.coins + reward.coins,
            boostRunsLeft = maxOf(state.boostRunsLeft, boost.runs),
            boostMultiplier = maxOf(state.boostMultiplier, boost.multiplier),
        )
    }

    /** The boost a streak of [streak] days buys. */
    fun boostFor(streak: Int): DailyBoost = when {
        streak >= 7 -> DailyBoost(2.00f, 5, "x2 score for 5 runs")
        streak >= 5 -> DailyBoost(1.75f, 4, "x1.75 score for 4 runs")
        streak >= 3 -> DailyBoost(1.50f, 3, "x1.5 score for 3 runs")
        streak >= 1 -> DailyBoost(1.25f, 2, "x1.25 score for 2 runs")
        else -> DailyBoost(1f, 0, "No boost yet")
    }

    /**
     * Consumes one run of the boost. Called when a run ends; returns the state
     * with the counter decremented and the multiplier cleared when it hits zero.
     */
    fun consumeBoostRun(state: DailyState): DailyState {
        if (state.boostRunsLeft <= 0) return state.copy(boostMultiplier = 1f)
        val left = state.boostRunsLeft - 1
        return state.copy(
            boostRunsLeft = left,
            boostMultiplier = if (left <= 0) 1f else state.boostMultiplier,
        )
    }

    /** Applies the active boost to a raw score, rounding down. */
    fun applyBoost(rawScore: Long, state: DailyState): Long =
        if (state.boostRunsLeft > 0) (rawScore * state.boostMultiplier).toLong() else rawScore
}
