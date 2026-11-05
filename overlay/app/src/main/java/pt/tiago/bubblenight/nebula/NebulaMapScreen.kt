package pt.tiago.bubblenight.nebula

import android.graphics.BitmapFactory
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import pt.tiago.bubblenight.data.RewardStore
import pt.tiago.bubblenight.game.Boosters
import pt.tiago.bubblenight.game.DailyRewards
import pt.tiago.bubblenight.game.DailyState
import pt.tiago.bubblenight.ui.UiCallbacks
import pt.tiago.bubblenight.ui.UiLevelNode
import pt.tiago.bubblenight.ui.UiModel
import java.time.LocalDate
import kotlin.math.cos
import kotlin.math.sin

/**
 * Nebula map: the orbit's levels laid out as a 3D constellation path.
 *
 * The map is drawn entirely from vectors and one generated planet bitmap, so it
 * scales to any screen and adds no per-orbit image weight beyond 12 PNGs.
 * Dragging rotates the camera; tapping a node opens its preparation card.
 */

private val Background = Color(0xFF0E1020)
private val BackgroundDeep = Color(0xFF07080F)
private val SurfaceColor = Color(0xFF24283B)
private val RaisedColor = Color(0xFF292E42)
private val TextColor = Color(0xFFC0CAF5)
private val StrongColor = Color(0xFFE2E8FF)
private val MutedColor = Color(0xFF8C94BE)
private val AccentColor = Color(0xFF7AA2F7)
private val PurpleColor = Color(0xFFBB9AF7)
private val CyanColor = Color(0xFF7DCFFF)
private val OrangeColor = Color(0xFFFF9E64)
private val LineColor = Color(0xFF414868)
private val OnAccent = Color(0xFF16161E)

/** Cached per-node projection so drawing and hit-testing agree exactly. */
private class NebulaLayout(
    val xs: FloatArray,
    val ys: FloatArray,
    val radius: FloatArray,
    val alpha: FloatArray,
    val starX: FloatArray,
    val starY: FloatArray,
    val starAlpha: FloatArray,
)

private const val BASE_NODE_RADIUS = 0.062f
private const val STAR_COUNT = 150

private fun computeLayout(
    nodeCount: Int,
    yaw: Float,
    pitch: Float,
    width: Float,
    height: Float,
    seconds: Float,
    starSeed: Int,
): NebulaLayout {
    val camera = NebulaCamera(yawDeg = yaw, pitchDeg = pitch, distance = 7f, focal = 2.2f)
    val pixelsPerUnit = minOf(width, height) * 0.74f
    val cx = width * 0.5f
    val cy = height * 0.52f

    val xs = FloatArray(nodeCount)
    val ys = FloatArray(nodeCount)
    val radius = FloatArray(nodeCount)
    val alpha = FloatArray(nodeCount)
    for (i in 0 until nodeCount) {
        val p = NebulaMath.project(NebulaMath.pathPoint(i, nodeCount), camera)
        if (!p.visible) {
            radius[i] = 0f
            continue
        }
        xs[i] = cx + p.x * pixelsPerUnit
        ys[i] = cy - p.y * pixelsPerUnit
        radius[i] = BASE_NODE_RADIUS * p.scale * pixelsPerUnit
        alpha[i] = NebulaMath.depthAlpha(p.depth)
    }

    val stars = NebulaMath.starField(STAR_COUNT, starSeed)
    val starX = FloatArray(stars.size)
    val starY = FloatArray(stars.size)
    val starAlpha = FloatArray(stars.size)
    for (i in stars.indices) {
        val p = NebulaMath.project(stars[i], camera)
        if (!p.visible) continue
        starX[i] = cx + p.x * pixelsPerUnit
        starY[i] = cy - p.y * pixelsPerUnit
        starAlpha[i] = NebulaMath.twinkle(i, seconds) * NebulaMath.depthAlpha(p.depth, floor = 0.15f)
    }
    return NebulaLayout(xs, ys, radius, alpha, starX, starY, starAlpha)
}

@Composable
fun NebulaMapScreen(model: UiModel, callbacks: UiCallbacks, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val density = LocalDensity.current
    val store = remember { RewardStore(context) }
    var daily by remember { mutableStateOf(store.load()) }
    var showRewards by remember { mutableStateOf(false) }
    var yaw by remember { mutableStateOf(-16f) }
    var pitch by remember { mutableStateOf(13f) }
    var seconds by remember { mutableStateOf(0f) }
    var pulseAt by remember { mutableStateOf(-1f) }
    var pulseIndex by remember { mutableStateOf(-1) }
    val reduced = model.reducedMotion

    // One frame clock drives the star twinkle, the camera drift and the tap pulse.
    LaunchedEffect(reduced) {
        if (reduced) {
            seconds = 0f
            return@LaunchedEffect
        }
        var start = 0L
        while (true) {
            withFrameNanos { now ->
                if (start == 0L) start = now
                seconds = (now - start) / 1_000_000_000f
            }
        }
    }

    val nodes = model.orbit?.nodes.orEmpty()
    val orbitNumber = model.orbitNumber.coerceIn(1, 12)
    val planet = remember(orbitNumber) { loadPlanetBitmap(context, orbitNumber) }
    val today = remember { LocalDate.now() }
    val canClaim = DailyRewards.canClaim(daily, today)

    val driftYaw = yaw + if (reduced) 0f else sin(seconds * 0.22f) * 5f
    val driftPitch = pitch + if (reduced) 0f else sin(seconds * 0.17f) * 1.6f

    BoxWithConstraints(modifier.fillMaxSize()) {
        val widthPx = with(density) { maxWidth.toPx() }
        val heightPx = with(density) { maxHeight.toPx() }
        val layout = remember(nodes.size, driftYaw, driftPitch, widthPx, heightPx, seconds) {
            computeLayout(nodes.size, driftYaw, driftPitch, widthPx, heightPx, seconds, starSeed = 7)
        }
        val layoutState = rememberUpdatedState(layout)

        Box(Modifier.fillMaxSize()) {
            Canvas(
                Modifier
                    .fillMaxSize()
                    .pointerInput(Unit) {
                        detectDragGestures { change, drag ->
                            change.consume()
                            yaw = (yaw + drag.x * 0.22f).coerceIn(-70f, 70f)
                            pitch = (pitch - drag.y * 0.10f).coerceIn(-6f, 34f)
                        }
                    }
                    .pointerInput(nodes.size) {
                        detectTapGestures { tap ->
                            val current = layoutState.value
                            val hit = NebulaMath.nearestNode(
                                tap.x, tap.y, current.xs, current.ys, current.radius,
                            )
                            if (hit >= 0 && hit < nodes.size) {
                                pulseIndex = hit
                                pulseAt = seconds
                                val node = nodes[hit]
                                if (node.state != UiLevelNode.NodeState.LOCKED) {
                                    callbacks.onOpenPreparation(node.id)
                                }
                            }
                        }
                    }
                    .semantics {
                        contentDescription = "Nebula map, ${nodes.size} levels. Drag to rotate, tap a star to play."
                    },
            ) {
                drawNebulaBackground(seconds, reduced)
                drawStars(layout)
                drawPath3d(layout)
                drawNodes(layout, nodes, seconds)
                drawPlanet(planet, seconds, reduced)
                drawPulse(layout, pulseIndex, pulseAt, seconds)
            }

            // Level numbers ride on top of the canvas as real text, so they stay
            // crisp at any density and remain readable to TalkBack.
            nodes.forEachIndexed { index, node ->
                if (index >= layout.radius.size) return@forEachIndexed
                val r = layout.radius[index]
                if (r <= 1f) return@forEachIndexed
                val d = with(density) { r.toDp() }
                val label = node.accessibleLabel ?: "Level ${node.number}"
                Box(
                    Modifier
                        .offset(
                            x = with(density) { layout.xs[index].toDp() } - d,
                            y = with(density) { layout.ys[index].toDp() } - d,
                        )
                        .size(d * 2f)
                        .semantics { contentDescription = label },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = node.number.toString(),
                        color = when (node.state) {
                            UiLevelNode.NodeState.CURRENT -> OnAccent
                            UiLevelNode.NodeState.LOCKED -> MutedColor.copy(alpha = 0.55f)
                            else -> StrongColor
                        },
                        fontSize = (r * 0.62f / density.density).sp,
                        fontWeight = FontWeight.SemiBold,
                        textAlign = TextAlign.Center,
                    )
                }
            }

            NebulaTopBar(
                title = model.orbit?.name ?: model.currentOrbitName,
                coins = daily.coins,
                onBack = callbacks::onBack,
            )

            Column(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                BoosterTray(orbit = orbitNumber, streak = daily.streak)
                DailyBar(
                    daily = daily,
                    canClaim = canClaim,
                    onClick = { showRewards = true },
                )
            }

            if (showRewards) {
                DailyRewardSheet(
                    daily = daily,
                    today = today,
                    onClaim = {
                        daily = store.claimToday(today)
                        pulseAt = seconds
                    },
                    onDismiss = { showRewards = false },
                )
            }
        }
    }
}

// --------------------------------------------------------------------------- //
// Drawing
// --------------------------------------------------------------------------- //

private fun DrawScope.drawNebulaBackground(seconds: Float, reduced: Boolean) {
    drawRect(
        Brush.verticalGradient(
            listOf(BackgroundDeep, Background, Color(0xFF141830)),
            startY = 0f,
            endY = size.height,
        ),
    )
    // Three soft clouds; they drift a few pixels so the sky is never static.
    val drift = if (reduced) 0f else sin(seconds * 0.11f) * size.width * 0.02f
    val clouds = listOf(
        Triple(Offset(size.width * 0.22f + drift, size.height * 0.24f), size.width * 0.55f, PurpleColor),
        Triple(Offset(size.width * 0.84f - drift, size.height * 0.38f), size.width * 0.48f, CyanColor),
        Triple(Offset(size.width * 0.45f, size.height * 0.86f + drift), size.width * 0.62f, AccentColor),
    )
    clouds.forEachIndexed { i, (center, radius, color) ->
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(color.copy(alpha = 0.16f - i * 0.03f), Color.Transparent),
                center = center,
                radius = radius,
            ),
            radius = radius,
            center = center,
        )
    }
}

private fun DrawScope.drawStars(layout: NebulaLayout) {
    for (i in layout.starX.indices) {
        val a = layout.starAlpha[i]
        if (a <= 0.01f) continue
        val x = layout.starX[i]
        val y = layout.starY[i]
        if (x < -20f || y < -20f || x > size.width + 20f || y > size.height + 20f) continue
        val r = 0.7f + (i % 3) * 0.55f
        drawCircle(Color.White.copy(alpha = a * 0.85f), r, Offset(x, y))
    }
}

private fun DrawScope.drawPath3d(layout: NebulaLayout) {
    val n = layout.radius.size
    if (n < 2) return
    val path = Path()
    var started = false
    for (i in 0 until n) {
        if (layout.radius[i] <= 0f) continue
        if (!started) {
            path.moveTo(layout.xs[i], layout.ys[i])
            started = true
        } else {
            path.lineTo(layout.xs[i], layout.ys[i])
        }
    }
    if (!started) return
    // Wide low-alpha pass reads as a glow; the thin pass is the actual thread.
    drawPath(path, AccentColor.copy(alpha = 0.10f), style = Stroke(width = 9f, cap = StrokeCap.Round))
    drawPath(path, AccentColor.copy(alpha = 0.45f), style = Stroke(width = 2f, cap = StrokeCap.Round))
    // Depth ticks: a bright bead on every node so the thread looks woven, not drawn.
    for (i in 0 until n) {
        if (layout.radius[i] <= 0f) continue
        drawCircle(Color.White.copy(alpha = 0.20f * layout.alpha[i]), 1.6f, Offset(layout.xs[i], layout.ys[i]))
    }
}

private fun DrawScope.drawNodes(layout: NebulaLayout, nodes: List<UiLevelNode>, seconds: Float) {
    nodes.forEachIndexed { index, node ->
        val r = layout.radius.getOrNull(index) ?: 0f
        if (r <= 0.5f) return@forEachIndexed
        val center = Offset(layout.xs[index], layout.ys[index])
        val a = layout.alpha[index]
        val fill: Color
        val ring: Color
        when (node.state) {
            UiLevelNode.NodeState.CURRENT -> {
                fill = CyanColor
                ring = Color.White
            }
            UiLevelNode.NodeState.COMPLETED -> {
                fill = PurpleColor.copy(alpha = 0.30f)
                ring = PurpleColor
            }
            UiLevelNode.NodeState.AVAILABLE -> {
                fill = RaisedColor
                ring = AccentColor
            }
            UiLevelNode.NodeState.LOCKED -> {
                fill = Color(0xFF1B1F33)
                ring = LineColor
            }
        }
        if (node.state == UiLevelNode.NodeState.CURRENT) {
            val pulse = 0.5f + 0.5f * sin(seconds * 2.4f)
            drawCircle(CyanColor.copy(alpha = 0.10f + 0.10f * pulse), r * (1.9f + 0.25f * pulse), center)
        }
        drawCircle(fill.copy(alpha = fill.alpha * a), r, center)
        drawCircle(ring.copy(alpha = a), r, center, style = Stroke(width = r * 0.14f))
        // Star pips under the node.
        if (node.stars > 0) {
            val pipR = r * 0.17f
            val gap = r * 0.55f
            val y = center.y + r * 1.55f
            for (s in 0 until 3) {
                val x = center.x + (s - 1) * gap
                val on = s < node.stars
                drawCircle(
                    if (on) OrangeColor.copy(alpha = a) else LineColor.copy(alpha = 0.5f * a),
                    pipR,
                    Offset(x, y),
                )
            }
        }
    }
}

private fun DrawScope.drawPlanet(bitmap: ImageBitmap?, seconds: Float, reduced: Boolean) {
    val radius = size.width * 0.30f
    val center = Offset(size.width * 0.86f, size.height * 0.10f)
    // Halo first, so the planet sits inside its own light.
    drawCircle(
        brush = Brush.radialGradient(
            colors = listOf(PurpleColor.copy(alpha = 0.20f), Color.Transparent),
            center = center,
            radius = radius * 1.7f,
        ),
        radius = radius * 1.7f,
        center = center,
    )
    if (bitmap != null) {
        val side = (radius * 2f).toInt().coerceAtLeast(1)
        drawImage(
            image = bitmap,
            dstOffset = IntOffset((center.x - radius).toInt(), (center.y - radius).toInt()),
            dstSize = IntSize(side, side),
            alpha = 0.95f,
        )
    } else {
        drawCircle(
            Brush.radialGradient(
                colors = listOf(Color(0xFF6C7BB8), Color(0xFF232A48)),
                center = center - Offset(radius * 0.35f, radius * 0.35f),
                radius = radius * 1.3f,
            ),
            radius,
            center,
        )
    }
    // A tilted ring drawn on top sells the 3D read more than the texture does.
    val tilt = if (reduced) 0.22f else 0.22f + sin(seconds * 0.35f) * 0.02f
    drawOval(
        color = CyanColor.copy(alpha = 0.35f),
        topLeft = Offset(center.x - radius * 1.65f, center.y - radius * tilt),
        size = Size(radius * 3.3f, radius * tilt * 2f),
        style = Stroke(width = 2f),
    )
}

private fun DrawScope.drawPulse(layout: NebulaLayout, index: Int, at: Float, seconds: Float) {
    if (index < 0 || index >= layout.radius.size) return
    val age = seconds - at
    if (age < 0f || age > 0.75f) return
    val t = age / 0.75f
    val r = layout.radius[index]
    if (r <= 0f) return
    val center = Offset(layout.xs[index], layout.ys[index])
    drawCircle(
        CyanColor.copy(alpha = (1f - t) * 0.55f),
        r * (1f + t * 2.6f),
        center,
        style = Stroke(width = 2.5f * (1f - t)),
    )
    for (i in 0 until 6) {
        val angle = i * 1.047f + t * 1.2f
        val dist = r * (1.2f + t * 2.4f)
        drawCircle(
            Color.White.copy(alpha = (1f - t) * 0.8f),
            r * 0.14f * (1f - t),
            Offset(center.x + cos(angle) * dist, center.y + sin(angle) * dist),
        )
    }
}

private fun loadPlanetBitmap(context: android.content.Context, orbit: Int): ImageBitmap? = runCatching {
    context.assets.open("nebula/planets/orbit_%02d.png".format(orbit)).use { stream ->
        BitmapFactory.decodeStream(stream)?.asImageBitmap()
    }
}.getOrNull()

// --------------------------------------------------------------------------- //
// Chrome
// --------------------------------------------------------------------------- //

@Composable
private fun NebulaTopBar(title: String, coins: Long, onBack: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier.size(44.dp).clip(CircleShape).background(SurfaceColor.copy(alpha = 0.85f))
                .clickable(onClick = onBack),
            contentAlignment = Alignment.Center,
        ) {
            Text("\u2039", color = TextColor, fontSize = 30.sp)
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text("NEBULA MAP", color = PurpleColor, fontSize = 11.sp, letterSpacing = 2.sp)
            Text(title, color = StrongColor, fontSize = 20.sp, fontWeight = FontWeight.Bold)
        }
        Surface(shape = RoundedCornerShape(14.dp), color = SurfaceColor.copy(alpha = 0.9f)) {
            Row(Modifier.padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("\u25c8", color = OrangeColor, fontSize = 14.sp)
                Spacer(Modifier.width(6.dp))
                Text(coins.toString(), color = StrongColor, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
            }
        }
    }
}

@Composable
private fun BoosterTray(orbit: Int, streak: Int) {
    val unlocked = Boosters.unlockedAt(orbit, streak)
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Boosters.all.take(5).forEach { spec ->
            val ready = spec.id in unlocked
            Box(
                Modifier.size(42.dp).clip(CircleShape)
                    .background(if (ready) RaisedColor else Color(0xFF1B1F33))
                    .border(1.dp, if (ready) PurpleColor.copy(alpha = 0.7f) else LineColor, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = spec.glyph,
                    fontSize = 17.sp,
                    color = if (ready) Color.White else MutedColor.copy(alpha = 0.4f),
                )
            }
        }
        Spacer(Modifier.weight(1f))
        Text(
            "${unlocked.size}/${Boosters.all.size} boosters",
            color = MutedColor,
            fontSize = 11.sp,
        )
    }
}

@Composable
private fun DailyBar(daily: DailyState, canClaim: Boolean, onClick: () -> Unit) {
    val reward = DailyRewards.rewardFor(daily.streak + 1)
    Surface(
        shape = RoundedCornerShape(18.dp),
        color = if (canClaim) Color(0xFF2B2350) else SurfaceColor.copy(alpha = 0.95f),
        modifier = Modifier.fillMaxWidth().heightIn(min = 62.dp).clickable(onClick = onClick),
    ) {
        Row(
            Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(if (canClaim) "\ud83c\udf81" else "\u2713", fontSize = 22.sp)
            Column(Modifier.weight(1f)) {
                Text(
                    if (canClaim) "Daily reward ready" else "Daily reward claimed",
                    color = StrongColor,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    if (daily.boostRunsLeft > 0) {
                        "x${trimZero(daily.boostMultiplier)} boost \u00b7 ${daily.boostRunsLeft} runs left"
                    } else {
                        "Day ${reward.day} of 7 \u00b7 streak ${daily.streak}"
                    },
                    color = MutedColor,
                    fontSize = 12.sp,
                )
            }
            Text("\u203a", color = MutedColor, fontSize = 22.sp)
        }
    }
}

private fun trimZero(value: Float): String =
    if (value == value.toInt().toFloat()) value.toInt().toString() else value.toString()

@Composable
private fun DailyRewardSheet(
    daily: DailyState,
    today: LocalDate,
    onClaim: () -> Unit,
    onDismiss: () -> Unit,
) {
    val canClaim = DailyRewards.canClaim(daily, today)
    val nextStreak = DailyRewards.streakIfClaimed(daily, today)
    val boost = DailyRewards.boostFor(nextStreak)
    Box(
        Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.6f)).clickable(onClick = onDismiss),
        contentAlignment = Alignment.BottomCenter,
    ) {
        Surface(
            shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp),
            color = SurfaceColor,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text("Daily rewards", color = StrongColor, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                Text(
                    "Streak ${daily.streak} \u00b7 best ${daily.bestStreak}",
                    color = MutedColor,
                    fontSize = 13.sp,
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    DailyRewards.table.forEach { slot ->
                        val active = slot.day == DailyRewards.rewardFor(nextStreak).day
                        val past = slot.day <= daily.streak % DailyRewards.CYCLE && daily.streak > 0
                        Column(
                            Modifier.weight(1f),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            Box(
                                Modifier.fillMaxWidth().heightIn(min = 54.dp)
                                    .clip(RoundedCornerShape(12.dp))
                                    .background(
                                        when {
                                            active -> PurpleColor.copy(alpha = 0.28f)
                                            past -> RaisedColor
                                            else -> Color(0xFF1B1F33)
                                        },
                                    )
                                    .border(
                                        1.dp,
                                        if (active) PurpleColor else LineColor,
                                        RoundedCornerShape(12.dp),
                                    ),
                                contentAlignment = Alignment.Center,
                            ) {
                                Text(
                                    slot.booster?.let { Boosters.byId(it).glyph } ?: "\u25c8",
                                    fontSize = 18.sp,
                                )
                            }
                            Text("${slot.day}", color = MutedColor, fontSize = 10.sp)
                        }
                    }
                }
                Text(
                    "Today: ${DailyRewards.rewardFor(nextStreak).label}",
                    color = TextColor,
                    fontSize = 14.sp,
                )
                Text(boost.label, color = CyanColor, fontSize = 13.sp)
                Surface(
                    shape = RoundedCornerShape(16.dp),
                    color = if (canClaim) PurpleColor else LineColor,
                    modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp).clickable {
                        if (canClaim) {
                            onClaim()
                            onDismiss()
                        } else {
                            onDismiss()
                        }
                    },
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Text(
                            if (canClaim) "Claim day $nextStreak" else "Come back tomorrow",
                            color = if (canClaim) OnAccent else MutedColor,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                }
            }
        }
    }
}
