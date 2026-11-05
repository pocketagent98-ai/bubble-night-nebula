package pt.tiago.bubblenight.nebula

import kotlin.math.cos
import kotlin.math.sin

/**
 * The 3D side of the Nebula map.
 *
 * Everything here is pure Kotlin with no Android or Compose types, so the whole
 * projection pipeline can be unit-tested on the JVM. The composable in
 * `NebulaMapScreen.kt` only turns these numbers into draw calls.
 */

/** A point in nebula space. Units are arbitrary; 1.0 is roughly one node spacing. */
data class Vec3(val x: Float, val y: Float, val z: Float)

/**
 * Pinhole camera. [yawDeg] turns the world around the vertical axis, [pitchDeg]
 * tilts it, [distance] pushes it away from the eye and [focal] is the lens
 * length. A larger focal length magnifies the scene.
 */
data class NebulaCamera(
    val yawDeg: Float = 0f,
    val pitchDeg: Float = 0f,
    val distance: Float = 7f,
    val focal: Float = 2.2f,
)

/**
 * Result of projecting one point. [scale] multiplies sprite radii, so a node
 * further away is drawn smaller with no extra maths at the call site.
 * A non-positive scale means the point sits behind the eye and must be skipped.
 */
data class Projected(val x: Float, val y: Float, val scale: Float, val depth: Float) {
    val visible: Boolean get() = scale > 0f
}

object NebulaMath {

    /** Closest a point may sit to the eye before it is culled. */
    const val NEAR_PLANE = 0.15f

    /** Projects [p] through [camera]. Screen coordinates are in camera units, not pixels. */
    fun project(p: Vec3, camera: NebulaCamera): Projected {
        val yaw = Math.toRadians(camera.yawDeg.toDouble())
        val pitch = Math.toRadians(camera.pitchDeg.toDouble())
        val cy = cos(yaw).toFloat()
        val sy = sin(yaw).toFloat()
        val cp = cos(pitch).toFloat()
        val sp = sin(pitch).toFloat()

        // Yaw around the vertical axis.
        val x1 = p.x * cy + p.z * sy
        val z1 = -p.x * sy + p.z * cy
        // Pitch around the horizontal axis.
        val y2 = p.y * cp - z1 * sp
        val z2 = p.y * sp + z1 * cp

        val zc = z2 + camera.distance
        if (zc <= NEAR_PLANE) return Projected(0f, 0f, -1f, zc)
        val s = camera.focal / zc
        return Projected(x1 * s, y2 * s, s, zc)
    }

    /**
     * Position of the [index]-th node on the serpentine constellation path.
     *
     * The path is a gentle S that also drifts towards and away from the viewer,
     * so a flat level list gains real parallax. [phase] rotates the whole path.
     */
    fun pathPoint(index: Int, count: Int, phase: Float = 0f): Vec3 {
        val t = if (count <= 1) 0f else index.toFloat() / (count - 1).toFloat()
        val a = t * PI_2_35 + phase
        val b = t * PI_1_15 + phase * 1.37f
        return Vec3(
            x = sin(a) * 1.55f,
            y = (0.5f - t) * 3.9f,
            z = sin(b) * 1.15f,
        )
    }

    /**
     * Distance fog for the path: near nodes stay bright, far ones sink into the
     * sky. Kept as a pure function so the look is tunable and testable.
     */
    fun depthAlpha(depth: Float, near: Float = 5.4f, far: Float = 9.6f, floor: Float = 0.38f): Float {
        val t = ((depth - near) / (far - near)).coerceIn(0f, 1f)
        return 1f - (1f - floor) * t
    }

    /**
     * Deterministic star field. Uses an explicit xorshift instead of [kotlin.random.Random]
     * so the same seed gives the same sky on every device and in tests.
     */
    fun starField(count: Int, seed: Int, spread: Float = 5.2f, depth: Float = 5.0f): List<Vec3> {
        val state = LongArray(1) { (seed.toLong() * 2654435761L) or 1L }
        fun next(): Float {
            var x = state[0]
            x = x xor (x shl 13)
            x = x xor (x ushr 7)
            x = x xor (x shl 17)
            state[0] = x
            return ((x ushr 40).toInt() and 0xFFFFFF) / 16777216f
        }
        return List(count) {
            Vec3(
                x = (next() - 0.5f) * spread,
                y = (next() - 0.5f) * spread,
                z = (next() - 0.5f) * depth,
            )
        }
    }

    /** Smooth acceleration for the camera drift and for node pop-in. */
    fun easeOutCubic(t: Float): Float {
        val c = t.coerceIn(0f, 1f)
        return 1f - (1f - c) * (1f - c) * (1f - c)
    }

    /** 0..1 twinkle for a star of [index] at time [seconds]. */
    fun twinkle(index: Int, seconds: Float): Float {
        val phase = (index * 0.7f) % (2f * PI_F)
        return 0.55f + 0.45f * sin(seconds * (0.8f + (index % 5) * 0.17f) + phase)
    }

    /**
     * Hit-test in screen pixels: returns the index of the nearest node whose
     * drawn radius covers ([px], [py]), or -1. [radiusOf] is the node radius in
     * pixels for that index, which the caller already knows from the projection.
     */
    fun nearestNode(
        px: Float,
        py: Float,
        screenX: FloatArray,
        screenY: FloatArray,
        radiusOf: FloatArray,
        slop: Float = 1.35f,
    ): Int {
        var best = -1
        var bestDistance = Float.MAX_VALUE
        for (i in screenX.indices) {
            if (radiusOf[i] <= 0f) continue
            val dx = px - screenX[i]
            val dy = py - screenY[i]
            val d = dx * dx + dy * dy
            val reach = radiusOf[i] * slop
            if (d <= reach * reach && d < bestDistance) {
                bestDistance = d
                best = i
            }
        }
        return best
    }

    private const val PI_F = 3.1415927f
    private const val PI_2_35 = 7.3822f
    private const val PI_1_15 = 3.6128f
}
