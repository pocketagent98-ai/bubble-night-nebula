package pt.tiago.bubblenight.nebula

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

class NebulaMathTest {

    @Test fun identityCameraProjectsTheOriginToTheCentre() {
        val p = NebulaMath.project(Vec3(0f, 0f, 0f), NebulaCamera(yawDeg = 0f, pitchDeg = 0f, distance = 7f, focal = 2.2f))
        assertTrue(p.visible)
        assertEquals(0f, p.x, 1e-5f)
        assertEquals(0f, p.y, 1e-5f)
        assertEquals(2.2f / 7f, p.scale, 1e-5f)
        assertEquals(7f, p.depth, 1e-5f)
    }

    @Test fun distanceShrinksTheProjectedScale() {
        val camera = NebulaCamera(distance = 7f)
        val near = NebulaMath.project(Vec3(0f, 0f, 1f), camera)
        val far = NebulaMath.project(Vec3(0f, 0f, -1f), camera)
        assertTrue(near.scale > far.scale)
        assertTrue(far.visible)
    }

    @Test fun pointsBehindTheEyeAreCulled() {
        val camera = NebulaCamera(distance = 7f)
        val behind = NebulaMath.project(Vec3(0f, 0f, -7f), camera)
        assertFalse(behind.visible)
    }

    @Test fun yawMovesThePointSidewaysButKeepsItVisible() {
        val camera = NebulaCamera(yawDeg = 0f, distance = 7f)
        val rotated = camera.copy(yawDeg = 45f)
        val p = Vec3(1.5f, 0f, 0f)
        val a = NebulaMath.project(p, camera)
        val b = NebulaMath.project(p, rotated)
        assertTrue(abs(a.x - b.x) > 0.05f)
        assertTrue(b.visible)
    }

    @Test fun pathIsDeterministicAndFitsTheFrustum() {
        val a = NebulaMath.pathPoint(10, 50)
        val b = NebulaMath.pathPoint(10, 50)
        assertEquals(a, b)
        for (i in 0 until 50) {
            val p = NebulaMath.pathPoint(i, 50)
            assertTrue("x in range at $i", abs(p.x) <= 1.6f)
            assertTrue("y in range at $i", abs(p.y) <= 2.0f)
            assertTrue("z in range at $i", abs(p.z) <= 1.2f)
            assertTrue("projected at $i", NebulaMath.project(p, NebulaCamera()).visible)
        }
    }

    @Test fun firstAndLastNodeSitAtOppositeEndsOfThePath() {
        val first = NebulaMath.pathPoint(0, 50)
        val last = NebulaMath.pathPoint(49, 50)
        assertEquals(1.95f, first.y, 1e-4f)
        assertEquals(-1.95f, last.y, 1e-4f)
    }

    @Test fun singleNodePathDoesNotDivideByZero() {
        val only = NebulaMath.pathPoint(0, 1)
        assertNotNull(only)
        assertEquals(0f, only.x, 1e-6f)
    }

    @Test fun depthAlphaFadesTowardsTheFloorAndClamps() {
        assertEquals(1f, NebulaMath.depthAlpha(5.0f), 1e-4f)
        assertEquals(0.38f, NebulaMath.depthAlpha(12f), 1e-4f)
        assertTrue(NebulaMath.depthAlpha(8f) < NebulaMath.depthAlpha(6f))
    }

    @Test fun starFieldIsStableForASeedAndVariesBetweenSeeds() {
        val a = NebulaMath.starField(20, 7)
        val b = NebulaMath.starField(20, 7)
        val c = NebulaMath.starField(20, 8)
        assertEquals(a, b)
        assertTrue(a != c)
        assertEquals(20, a.size)
    }

    @Test fun nearestNodePicksTheClosestHitAndIgnoresMisses() {
        val xs = floatArrayOf(100f, 200f, 300f)
        val ys = floatArrayOf(100f, 100f, 100f)
        val radii = floatArrayOf(20f, 20f, 20f)
        assertEquals(1, NebulaMath.nearestNode(205f, 102f, xs, ys, radii))
        assertEquals(-1, NebulaMath.nearestNode(50f, 400f, xs, ys, radii))
        assertEquals(-1, NebulaMath.nearestNode(100f, 100f, floatArrayOf(0f), floatArrayOf(0f), floatArrayOf(0f)))
    }

    @Test fun twinkleStaysInsideItsBand() {
        for (i in 0 until 30) {
            val v = NebulaMath.twinkle(i, i * 0.37f)
            assertTrue("twinkle $i = $v", v >= 0.09f && v <= 1.01f)
        }
    }
}
