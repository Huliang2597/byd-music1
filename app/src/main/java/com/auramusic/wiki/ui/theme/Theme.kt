package com.auramusic.wiki.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

val Rose = Color(0xFFE5485F)
val Coral = Color(0xFFFF7A59)
val Violet = Color(0xFF8E3BBF)
val Mint = Color(0xFF2FB58A)
val Amber = Color(0xFFF2A33A)

private val Light = lightColorScheme(
    primary = Rose,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFFE1E5),
    onPrimaryContainer = Color(0xFF5C0A1C),
    secondary = Color(0xFF7D4FB8),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFF0E2FF),
    onSecondaryContainer = Color(0xFF2E0B57),
    tertiary = Color(0xFFE0693A),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFE3D6),
    onTertiaryContainer = Color(0xFF4A1700),
    background = Color(0xFFFBF8F7),
    onBackground = Color(0xFF1E1A1B),
    surface = Color(0xFFFBF8F7),
    onSurface = Color(0xFF1E1A1B),
    surfaceVariant = Color(0xFFF2E6E8),
    onSurfaceVariant = Color(0xFF6B5E61),
    surfaceContainerLowest = Color.White,
    surfaceContainerLow = Color(0xFFFFFFFF),
    surfaceContainer = Color(0xFFF6F0F0),
    surfaceContainerHigh = Color(0xFFF0E8E9),
    surfaceContainerHighest = Color(0xFFEAE1E2),
    outline = Color(0xFFD3C4C7),
    outlineVariant = Color(0xFFEDE2E4),
    error = Color(0xFFD32F45),
    errorContainer = Color(0xFFFFDADC),
)

private val Dark = darkColorScheme(
    primary = Color(0xFFFF8A9A),
    onPrimary = Color(0xFF4A0716),
    primaryContainer = Color(0xFF6D1E30),
    onPrimaryContainer = Color(0xFFFFD9DE),
    secondary = Color(0xFFD7B8FF),
    onSecondary = Color(0xFF3F1772),
    secondaryContainer = Color(0xFF55308A),
    onSecondaryContainer = Color(0xFFF0E2FF),
    tertiary = Color(0xFFFFB693),
    onTertiary = Color(0xFF5A1D00),
    tertiaryContainer = Color(0xFF7A3414),
    onTertiaryContainer = Color(0xFFFFDBCB),
    background = Color(0xFF141113),
    onBackground = Color(0xFFEDE0E2),
    surface = Color(0xFF141113),
    onSurface = Color(0xFFEDE0E2),
    surfaceVariant = Color(0xFF3A3134),
    onSurfaceVariant = Color(0xFFC7B8BB),
    surfaceContainerLowest = Color(0xFF0F0C0D),
    surfaceContainerLow = Color(0xFF1E191B),
    surfaceContainer = Color(0xFF241F21),
    surfaceContainerHigh = Color(0xFF2E282A),
    surfaceContainerHighest = Color(0xFF393234),
    outline = Color(0xFF55494C),
    outlineVariant = Color(0xFF3A3134),
    error = Color(0xFFFFB3B8),
    errorContainer = Color(0xFF7A1A28),
)

@Immutable
data class Brand(val gradient: Brush, val glow: Color, val success: Color, val warning: Color)

val LocalBrand = staticCompositionLocalOf {
    Brand(Brush.linearGradient(listOf(Coral, Rose, Violet)), Rose, Mint, Amber)
}

private val base = Typography()
private val AppTypography = Typography(
    displaySmall = base.displaySmall.copy(fontWeight = FontWeight.Black, letterSpacing = (-0.5).sp),
    headlineMedium = base.headlineMedium.copy(fontWeight = FontWeight.Bold, letterSpacing = (-0.3).sp),
    headlineSmall = base.headlineSmall.copy(fontWeight = FontWeight.Bold),
    titleLarge = base.titleLarge.copy(fontWeight = FontWeight.Bold),
    titleMedium = base.titleMedium.copy(fontWeight = FontWeight.SemiBold),
    titleSmall = base.titleSmall.copy(fontWeight = FontWeight.SemiBold),
    bodyLarge = base.bodyLarge.copy(lineHeight = 24.sp),
    bodyMedium = base.bodyMedium.copy(lineHeight = 21.sp),
    bodySmall = base.bodySmall.copy(lineHeight = 18.sp),
    labelLarge = base.labelLarge.copy(fontWeight = FontWeight.SemiBold),
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(18.dp),
    large = RoundedCornerShape(26.dp),
    extraLarge = RoundedCornerShape(32.dp),
)

val MonoStyle = TextStyle(fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace, fontSize = 13.sp, lineHeight = 20.sp)

@Composable
fun WikiTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val colors = if (dark) Dark else Light
    MaterialTheme(colorScheme = colors, typography = AppTypography, shapes = AppShapes) {
        androidx.compose.runtime.CompositionLocalProvider(
            LocalBrand provides Brand(
                gradient = Brush.linearGradient(listOf(Coral, Rose, Violet)),
                glow = colors.primary,
                success = if (dark) Color(0xFF6FDDB4) else Mint,
                warning = if (dark) Color(0xFFFFC978) else Amber,
            ),
            content = content,
        )
    }
}
