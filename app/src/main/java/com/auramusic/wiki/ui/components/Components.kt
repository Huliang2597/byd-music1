package com.auramusic.wiki.ui.components

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.ChevronLeft
import androidx.compose.material.icons.rounded.ChevronRight
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.ErrorOutline
import androidx.compose.material.icons.rounded.Inbox
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil.compose.SubcomposeAsyncImage
import com.auramusic.wiki.ui.theme.LocalBrand

/** 全局轻提示。 */
val LocalToast = staticCompositionLocalOf<(String) -> Unit> { {} }

/** 系统关闭动画（动画缩放为 0）时跳过入场动效。 */
val LocalReduceMotion = staticCompositionLocalOf { false }

// ---------------------------------------------------------------- 动效

/** 按压时轻微缩放，松手弹回。 */
fun Modifier.pressScale(interaction: MutableInteractionSource, pressed: Float = 0.96f): Modifier = composed {
    val isPressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(
        if (isPressed) pressed else 1f,
        tween(120),
        label = "press",
    )
    this.graphicsLayer { scaleX = scale; scaleY = scale }
}

/** 列表项首次出现时淡入，按序号轻微错开（不做位移，避免跳动感）。 */
fun Modifier.enterAnimation(index: Int = 0, key: Any? = Unit): Modifier = composed {
    if (LocalReduceMotion.current) return@composed this
    val progress = remember(key) { Animatable(0f) }
    LaunchedEffect(key) {
        kotlinx.coroutines.delay((index.coerceAtMost(8) * 30).toLong())
        progress.animateTo(1f, tween(260, easing = FastOutSlowInEasing))
    }
    this.graphicsLayer { alpha = progress.value }
}

/** 骨架屏的流光效果。 */
fun Modifier.shimmer(shape: androidx.compose.ui.graphics.Shape = RoundedCornerShape(12.dp)): Modifier = composed {
    val base = MaterialTheme.colorScheme.surfaceContainerHighest
    val highlight = MaterialTheme.colorScheme.surfaceContainerLow
    val transition = rememberInfiniteTransition(label = "shimmer")
    val x by transition.animateFloat(
        -1f, 2f,
        infiniteRepeatable(tween(1300, easing = LinearEasing), RepeatMode.Restart),
        label = "shimmerX",
    )
    this
        .clip(shape)
        .background(
            Brush.linearGradient(
                listOf(base, highlight, base),
                start = Offset(x * 600f, 0f),
                end = Offset(x * 600f + 600f, 300f),
            ),
        )
}

// ---------------------------------------------------------------- 容器

@Composable
fun SectionCard(
    title: String?,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    trailing: (@Composable RowScope.() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surfaceContainerLow,
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
        shadowElevation = 0.dp,
    ) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (title != null) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                Modifier
                                    .size(width = 4.dp, height = 16.dp)
                                    .clip(CircleShape)
                                    .background(LocalBrand.current.gradient),
                            )
                            Spacer(Modifier.width(8.dp))
                            Text(title, style = MaterialTheme.typography.titleMedium)
                        }
                        if (subtitle != null) {
                            Spacer(Modifier.height(4.dp))
                            Text(
                                subtitle,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    trailing?.invoke(this)
                }
            }
            content()
        }
    }
}

/** 页面顶部的大标题，带品牌渐变光晕。 */
@Composable
fun PageHeader(
    title: String,
    subtitle: String? = null,
    onBack: (() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {},
) {
    val gradient = LocalBrand.current.gradient
    Box(
        Modifier
            .fillMaxWidth()
            .drawBehind {
                val radius = 84.dp.toPx()
                drawCircle(gradient, radius, Offset(size.width - 24.dp.toPx(), -16.dp.toPx()), alpha = 0.16f)
            },
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(start = if (onBack != null) 6.dp else 20.dp, end = 12.dp, top = 12.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (onBack != null) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "返回")
                }
                Spacer(Modifier.width(2.dp))
            }
            Column(Modifier.weight(1f)) {
                Text(
                    title,
                    style = if (onBack != null) MaterialTheme.typography.titleLarge else MaterialTheme.typography.headlineMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (subtitle != null) {
                    Text(
                        subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            actions()
        }
    }
}

// ---------------------------------------------------------------- 按钮

@Composable
fun GradientButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    loading: Boolean = false,
    icon: ImageVector? = null,
) {
    val interaction = remember { MutableInteractionSource() }
    val alpha by animateFloatAsState(if (enabled) 1f else 0.45f, label = "btnAlpha")
    Box(
        modifier
            .heightIn(min = 52.dp)
            .pressScale(interaction)
            .graphicsLayer { this.alpha = alpha }
            .clip(RoundedCornerShape(26.dp))
            .background(LocalBrand.current.gradient)
            .clickable(interaction, indication = androidx.compose.material3.ripple(color = Color.White), enabled = enabled && !loading, onClick = onClick)
            .padding(horizontal = 22.dp, vertical = 14.dp),
        contentAlignment = Alignment.Center,
    ) {
        AnimatedContent(loading, transitionSpec = { fadeIn(tween(180)) togetherWith fadeOut(tween(120)) }, label = "btn") { busy ->
            CompositionLocalProvider(LocalContentColor provides Color.White) {
                if (busy) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(Modifier.size(18.dp), color = Color.White, strokeWidth = 2.dp)
                        Spacer(Modifier.width(10.dp))
                        Text(text, style = MaterialTheme.typography.labelLarge, color = Color.White)
                    }
                } else {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        if (icon != null) {
                            Icon(icon, null, Modifier.size(18.dp), tint = Color.White)
                            Spacer(Modifier.width(8.dp))
                        }
                        Text(text, style = MaterialTheme.typography.labelLarge, color = Color.White)
                    }
                }
            }
        }
    }
}

@Composable
fun SoftButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    icon: ImageVector? = null,
    contentPadding: PaddingValues = PaddingValues(horizontal = 16.dp, vertical = 11.dp),
) {
    val interaction = remember { MutableInteractionSource() }
    val container = MaterialTheme.colorScheme.primaryContainer
    val content = MaterialTheme.colorScheme.onPrimaryContainer
    Row(
        modifier
            .pressScale(interaction)
            .graphicsLayer { alpha = if (enabled) 1f else 0.45f }
            .clip(RoundedCornerShape(22.dp))
            .background(container)
            .clickable(interaction, indication = androidx.compose.material3.ripple(), enabled = enabled, onClick = onClick)
            .padding(contentPadding),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        if (icon != null) {
            Icon(icon, null, Modifier.size(18.dp), tint = content)
            Spacer(Modifier.width(6.dp))
        }
        Text(text, style = MaterialTheme.typography.labelLarge, color = content, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

// ---------------------------------------------------------------- 输入

@Composable
fun AppTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    placeholder: String? = null,
    supporting: String? = null,
    singleLine: Boolean = true,
    minLines: Int = 1,
    maxLines: Int = if (singleLine) 1 else 12,
    enabled: Boolean = true,
    required: Boolean = false,
    error: String? = null,
    leading: ImageVector? = null,
    trailing: (@Composable () -> Unit)? = null,
    keyboardType: KeyboardType = KeyboardType.Text,
    imeAction: ImeAction = ImeAction.Default,
    onIme: (() -> Unit)? = null,
    textStyle: androidx.compose.ui.text.TextStyle = MaterialTheme.typography.bodyLarge,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier.fillMaxWidth(),
        label = { Text(if (required) "$label *" else label) },
        placeholder = placeholder?.let { { Text(it) } },
        supportingText = (error ?: supporting)?.let { { Text(it) } },
        isError = error != null,
        singleLine = singleLine,
        minLines = minLines,
        maxLines = maxLines,
        enabled = enabled,
        textStyle = textStyle,
        leadingIcon = leading?.let { { Icon(it, null) } },
        trailingIcon = trailing,
        shape = RoundedCornerShape(16.dp),
        keyboardOptions = KeyboardOptions(keyboardType = keyboardType, imeAction = imeAction),
        keyboardActions = KeyboardActions(onAny = { onIme?.invoke() }),
        colors = OutlinedTextFieldDefaults.colors(
            unfocusedBorderColor = MaterialTheme.colorScheme.outlineVariant,
            unfocusedContainerColor = MaterialTheme.colorScheme.surfaceContainer.copy(alpha = 0.5f),
            focusedContainerColor = MaterialTheme.colorScheme.surfaceContainerLowest,
            disabledContainerColor = MaterialTheme.colorScheme.surfaceContainer.copy(alpha = 0.35f),
            disabledBorderColor = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f),
        ),
    )
}

/** 只读字段：点击后打开选择器。 */
@Composable
fun SelectorField(
    label: String,
    values: List<String>,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    placeholder: String = "点击选择",
    enabled: Boolean = true,
    required: Boolean = false,
    onRemove: ((Int) -> Unit)? = null,
) {
    val interaction = remember { MutableInteractionSource() }
    Column(modifier.fillMaxWidth()) {
        Text(
            if (required) "$label *" else label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(start = 4.dp, bottom = 6.dp),
        )
        Box(
            Modifier
                .fillMaxWidth()
                .heightIn(min = 54.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(MaterialTheme.colorScheme.surfaceContainer.copy(alpha = if (enabled) 0.6f else 0.3f))
                .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(16.dp))
                .clickable(interaction, androidx.compose.material3.ripple(), enabled = enabled, onClick = onClick)
                .padding(horizontal = 12.dp, vertical = 10.dp),
            contentAlignment = Alignment.CenterStart,
        ) {
            AnimatedContent(values.isEmpty(), label = "selector") { empty ->
                if (empty) {
                    Text(
                        placeholder,
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = if (enabled) 0.8f else 0.5f),
                        modifier = Modifier.padding(horizontal = 4.dp),
                    )
                } else {
                    FlowRowCompat(spacing = 8.dp) {
                        values.forEachIndexed { index, value ->
                            Pill(
                                value,
                                onRemove = if (enabled && onRemove != null) ({ onRemove(index) }) else null,
                            )
                        }
                    }
                }
            }
        }
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
fun FlowRowCompat(spacing: Dp = 8.dp, content: @Composable () -> Unit) {
    androidx.compose.foundation.layout.FlowRow(
        horizontalArrangement = Arrangement.spacedBy(spacing),
        verticalArrangement = Arrangement.spacedBy(spacing),
    ) { content() }
}

@Composable
fun Pill(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = MaterialTheme.colorScheme.secondaryContainer,
    contentColor: Color = MaterialTheme.colorScheme.onSecondaryContainer,
    onRemove: (() -> Unit)? = null,
) {
    Row(
        modifier
            .clip(CircleShape)
            .background(color)
            .padding(start = 12.dp, end = if (onRemove != null) 4.dp else 12.dp, top = 6.dp, bottom = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(text, style = MaterialTheme.typography.labelLarge, color = contentColor, maxLines = 1, overflow = TextOverflow.Ellipsis)
        if (onRemove != null) {
            Spacer(Modifier.width(2.dp))
            Icon(
                Icons.Rounded.Close,
                contentDescription = "移除",
                tint = contentColor,
                modifier = Modifier
                    .size(20.dp)
                    .clip(CircleShape)
                    .clickable(onClick = onRemove)
                    .padding(3.dp),
            )
        }
    }
}

/** 状态标签，颜色随状态渐变。 */
@Composable
fun StatusPill(text: String, tone: Tone) {
    val brand = LocalBrand.current
    val scheme = MaterialTheme.colorScheme
    val target = when (tone) {
        Tone.Success -> brand.success
        Tone.Warning -> brand.warning
        Tone.Danger -> scheme.error
        Tone.Info -> scheme.secondary
        Tone.Neutral -> scheme.onSurfaceVariant
    }
    val color by animateColorAsState(target, label = "status")
    Text(
        text,
        style = MaterialTheme.typography.labelMedium,
        color = color,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier
            .clip(CircleShape)
            .background(color.copy(alpha = 0.14f))
            .padding(horizontal = 10.dp, vertical = 4.dp),
    )
}

enum class Tone { Success, Warning, Danger, Info, Neutral }

// ---------------------------------------------------------------- 状态

@Composable
fun EmptyState(text: String, modifier: Modifier = Modifier, icon: ImageVector = Icons.Rounded.Inbox) {
    Column(
        modifier
            .fillMaxWidth()
            .padding(vertical = 28.dp)
            .enterAnimation(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            Modifier
                .size(72.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.6f)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(icon, null, Modifier.size(34.dp), tint = MaterialTheme.colorScheme.primary)
        }
        Spacer(Modifier.height(12.dp))
        Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
    }
}

@Composable
fun ErrorState(text: String, onRetry: (() -> Unit)?, modifier: Modifier = Modifier) {
    Column(
        modifier
            .fillMaxWidth()
            .padding(vertical = 24.dp)
            .enterAnimation(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            Modifier
                .size(64.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.7f)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Rounded.ErrorOutline, null, Modifier.size(30.dp), tint = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(12.dp))
        Text(text, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center, modifier = Modifier.padding(horizontal = 24.dp))
        if (onRetry != null) {
            Spacer(Modifier.height(12.dp))
            SoftButton("重试", onRetry, icon = Icons.Rounded.Refresh)
        }
    }
}

/** 列表加载中的骨架。 */
@Composable
fun SkeletonList(count: Int = 4, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        repeat(count) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .clip(MaterialTheme.shapes.large)
                    .background(MaterialTheme.colorScheme.surfaceContainerLow)
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(Modifier.size(48.dp).shimmer(RoundedCornerShape(14.dp)))
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(Modifier.fillMaxWidth(0.7f).height(14.dp).shimmer())
                    Box(Modifier.fillMaxWidth(0.45f).height(12.dp).shimmer())
                }
            }
        }
    }
}

@Composable
fun Pager(page: Int, totalPages: Int, onPage: (Int) -> Unit, summary: String? = null) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            summary ?: "第 ${page + 1} / ${totalPages.coerceAtLeast(1)} 页",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(1f),
        )
        FilledTonalIconButton(onClick = { onPage(page - 1) }, enabled = page > 0) {
            Icon(Icons.Rounded.ChevronLeft, contentDescription = "上一页")
        }
        Spacer(Modifier.width(6.dp))
        FilledTonalIconButton(onClick = { onPage(page + 1) }, enabled = page + 1 < totalPages) {
            Icon(Icons.Rounded.ChevronRight, contentDescription = "下一页")
        }
    }
}

/** 进度条：带数值的渐变进度。 */
@Composable
fun GradientProgress(progress: Float, modifier: Modifier = Modifier) {
    val animated by animateFloatAsState(progress.coerceIn(0f, 1f), tween(300), label = "progress")
    Box(
        modifier
            .fillMaxWidth()
            .height(6.dp)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.surfaceContainerHighest),
    ) {
        Box(
            Modifier
                .fillMaxWidth(animated)
                .height(6.dp)
                .clip(CircleShape)
                .background(LocalBrand.current.gradient),
        )
    }
}

/** 网络图片，加载中显示流光，失败显示首字。 */
@Composable
fun RemoteImage(
    url: String?,
    contentDescription: String?,
    modifier: Modifier,
    shape: androidx.compose.ui.graphics.Shape = RoundedCornerShape(14.dp),
    fallback: String? = null,
) {
    Box(modifier.clip(shape).background(MaterialTheme.colorScheme.primaryContainer), contentAlignment = Alignment.Center) {
        val initial = @Composable {
            if (fallback != null) {
                Text(
                    fallback.take(1).ifBlank { "?" },
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                )
            }
        }
        if (url == null) {
            initial()
        } else {
            SubcomposeAsyncImage(
                model = coil.request.ImageRequest.Builder(androidx.compose.ui.platform.LocalContext.current)
                    .data(url).crossfade(260).build(),
                contentDescription = contentDescription,
                contentScale = ContentScale.Crop,
                modifier = Modifier.matchParentSize(),
                loading = { Box(Modifier.matchParentSize().shimmer(shape)) },
                error = { initial() },
            )
        }
    }
}

/** 可展开区域。 */
@Composable
fun Reveal(visible: Boolean, content: @Composable () -> Unit) {
    AnimatedVisibility(
        visible,
        enter = fadeIn(tween(220)) + expandVertically(spring(stiffness = Spring.StiffnessMediumLow)),
        exit = fadeOut(tween(150)) + shrinkVertically(tween(220)),
    ) { content() }
}

@Composable
fun InfoRow(label: String, value: String) {
    if (value.isBlank()) return
    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(84.dp).padding(top = 1.dp),
        )
        androidx.compose.foundation.text.selection.SelectionContainer(Modifier.weight(1f)) {
            Text(value, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
fun Hint(text: String) {
    Text(text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}
