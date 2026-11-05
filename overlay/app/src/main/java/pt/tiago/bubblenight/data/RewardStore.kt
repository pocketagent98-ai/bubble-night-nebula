package pt.tiago.bubblenight.data

import android.content.Context
import pt.tiago.bubblenight.game.DailyRewards
import pt.tiago.bubblenight.game.DailyState
import java.time.LocalDate

/**
 * Persistence for the Nebula daily layer.
 *
 * Deliberately separate from [Profile]: the reward streak is a convenience
 * layer, and putting it in the profile would force a schema migration on a
 * format that ships with checksums, backups and a recovery copy. SharedPreferences
 * keeps the blast radius at zero — if this file is corrupt, the game forgets a
 * streak and nothing else.
 */
class RewardStore(context: Context) {

    private val prefs = context.applicationContext
        .getSharedPreferences("nebula_rewards", Context.MODE_PRIVATE)

    fun load(): DailyState = DailyState(
        lastClaimIso = prefs.getString(KEY_LAST, null),
        streak = prefs.getInt(KEY_STREAK, 0),
        bestStreak = prefs.getInt(KEY_BEST, 0),
        coins = prefs.getLong(KEY_COINS, 0L),
        boostRunsLeft = prefs.getInt(KEY_BOOST_RUNS, 0),
        boostMultiplier = prefs.getFloat(KEY_BOOST_MULT, 1f),
    )

    fun save(state: DailyState) {
        prefs.edit()
            .putString(KEY_LAST, state.lastClaimIso)
            .putInt(KEY_STREAK, state.streak)
            .putInt(KEY_BEST, state.bestStreak)
            .putLong(KEY_COINS, state.coins)
            .putInt(KEY_BOOST_RUNS, state.boostRunsLeft)
            .putFloat(KEY_BOOST_MULT, state.boostMultiplier)
            .apply()
    }

    /** Claims today's reward if it is still unclaimed, persists it, and returns the new state. */
    fun claimToday(today: LocalDate = LocalDate.now()): DailyState {
        val current = load()
        val claimed = DailyRewards.claim(current, today)
        if (claimed != current) save(claimed)
        return claimed
    }

    fun addCoins(amount: Long): DailyState {
        val current = load()
        val updated = current.copy(coins = (current.coins + amount).coerceAtLeast(0L))
        save(updated)
        return updated
    }

    /** Called at the end of a scored run so the boost is spent exactly once. */
    fun consumeBoostRun(): DailyState {
        val current = load()
        val updated = DailyRewards.consumeBoostRun(current)
        if (updated != current) save(updated)
        return updated
    }

    private companion object {
        const val KEY_LAST = "lastClaimIso"
        const val KEY_STREAK = "streak"
        const val KEY_BEST = "bestStreak"
        const val KEY_COINS = "coins"
        const val KEY_BOOST_RUNS = "boostRunsLeft"
        const val KEY_BOOST_MULT = "boostMultiplier"
    }
}
