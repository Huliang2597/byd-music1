package com.auramusic.wiki.ui.screens

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.net.Uri
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Cookie
import androidx.compose.material.icons.rounded.Language
import androidx.compose.material.icons.rounded.QrCode2
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.VerifiedUser
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.auramusic.wiki.AppGraph
import com.auramusic.wiki.data.NeteaseAuth
import com.auramusic.wiki.data.QrState
import com.auramusic.wiki.ui.LocalNav
import com.auramusic.wiki.ui.components.AppTextField
import com.auramusic.wiki.ui.components.GradientButton
import com.auramusic.wiki.ui.components.Hint
import com.auramusic.wiki.ui.components.LocalToast
import com.auramusic.wiki.ui.components.Reveal
import com.auramusic.wiki.ui.components.SectionCard
import com.auramusic.wiki.ui.components.SoftButton
import com.auramusic.wiki.ui.components.enterAnimation
import com.auramusic.wiki.ui.theme.LocalBrand
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import java.net.SocketTimeoutException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

@Composable
fun LoginScreen(graph: AppGraph) {
    val toast = LocalToast.current
    val nav = LocalNav.current
    var mode by rememberSaveable { mutableIntStateOf(0) }
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .statusBarsPadding()
            .padding(horizontal = 20.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Hero()
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth().enterAnimation(1)) {
            listOf("扫码登录" to Icons.Rounded.QrCode2, "Cookie 登录" to Icons.Rounded.Cookie).forEachIndexed { index, (label, icon) ->
                SegmentedButton(
                    selected = mode == index,
                    onClick = { mode = index },
                    shape = SegmentedButtonDefaults.itemShape(index, 2),
                    colors = SegmentedButtonDefaults.colors(
                        activeContainerColor = MaterialTheme.colorScheme.primaryContainer,
                        activeContentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                    ),
                    icon = { Icon(icon, null, Modifier.size(18.dp)) },
                ) { Text(label) }
            }
        }
        AnimatedContent(
            mode,
            transitionSpec = {
                val dir = if (targetState > initialState) 1 else -1
                (slideInHorizontally(tween(320)) { it / 5 * dir } + fadeIn(tween(260)))
                    .togetherWith(slideOutHorizontally(tween(260)) { -it / 5 * dir } + fadeOut(tween(160)))
            },
            label = "loginMode",
            modifier = Modifier.enterAnimation(2),
        ) { m ->
            if (m == 0) QrLogin(graph) else CookieLogin(graph)
        }
        SoftButton(
            "官网登录 · 完成网页验证",
            {
                nav.officialLogin = { result ->
                    runCatching { graph.session.accept(result) }
                        .onSuccess { toast("已登录：${it.nickname}") }
                        .onFailure { toast(it.message ?: "登录失败") }
                }
            },
            Modifier.fillMaxWidth().enterAnimation(3),
            icon = Icons.Rounded.Language,
        )
        Row(Modifier.enterAnimation(4), verticalAlignment = Alignment.Top) {
            Icon(Icons.Rounded.VerifiedUser, null, Modifier.size(16.dp).padding(top = 2.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.width(6.dp))
            Hint("凭据仅在本机保存并发往网易云。扫码受限时，可用上方官网登录完成验证。")
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun Hero() {
    val transition = rememberInfiniteTransition(label = "hero")
    val spin by transition.animateFloat(0f, 360f, infiniteRepeatable(tween(14000)), label = "spin")
    val pulse by transition.animateFloat(0.92f, 1.04f, infiniteRepeatable(tween(2200, easing = FastOutSlowInEasing), RepeatMode.Reverse), label = "pulse")
    Box(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(32.dp))
            .background(LocalBrand.current.gradient)
            .padding(24.dp)
            .enterAnimation(0),
    ) {
        Box(
            Modifier
                .align(Alignment.TopEnd)
                .size(140.dp)
                .graphicsLayer { translationX = 70f; translationY = -60f; scaleX = pulse; scaleY = pulse }
                .clip(CircleShape)
                .background(Color.White.copy(alpha = 0.12f)),
        )
        Column {
            Box(
                Modifier
                    .size(64.dp)
                    .graphicsLayer { rotationZ = spin }
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = 0.95f)),
                contentAlignment = Alignment.Center,
            ) {
                Box(Modifier.size(40.dp).clip(CircleShape).background(Color(0xFF1E1A1B)), contentAlignment = Alignment.Center) {
                    Box(Modifier.size(12.dp).clip(CircleShape).background(Color.White))
                }
            }
            Spacer(Modifier.height(18.dp))
            Text("曲库共建", style = MaterialTheme.typography.displaySmall, color = Color.White)
            Spacer(Modifier.height(8.dp))
            Text(
                "补充网易云缺失的专辑和歌曲、完善歌曲资料与歌词、领取云小编任务。提交内容由网易云曲库审核。",
                style = MaterialTheme.typography.bodyMedium,
                color = Color.White.copy(alpha = 0.9f),
            )
        }
    }
}

private fun qrBitmap(text: String, size: Int = 640): Bitmap {
    val matrix = QRCodeWriter().encode(text, BarcodeFormat.QR_CODE, size, size, mapOf(EncodeHintType.MARGIN to 1))
    val pixels = IntArray(size * size) { i -> if (matrix[i % size, i / size]) 0xFF1E1A1B.toInt() else 0xFFFFFFFF.toInt() }
    return Bitmap.createBitmap(pixels, size, size, Bitmap.Config.ARGB_8888)
}

@Composable
private fun QrLogin(graph: AppGraph) {
    val toast = LocalToast.current
    var key by remember { mutableStateOf<String?>(null) }
    var image by remember { mutableStateOf<Bitmap?>(null) }
    var status by remember { mutableStateOf("正在获取二维码…") }
    var stopped by remember { mutableStateOf(false) }
    var verifying by remember { mutableStateOf(false) }
    var round by remember { mutableIntStateOf(0) }

    LaunchedEffect(round) {
        stopped = false
        verifying = false
        key = null
        image = null
        status = "正在获取二维码…"
        val created = runCatching { graph.session.createQrKey() }
        val unikey = created.getOrElse {
            status = it.message ?: "获取失败"
            stopped = true
            return@LaunchedEffect
        }
        image = withContext(Dispatchers.Default) { qrBitmap(NeteaseAuth.qrUrl(unikey)) }
        key = unikey
        status = "用网易云音乐 App 扫码"
        while (true) {
            delay(2000)
            val result = runCatching { graph.session.checkQr(unikey) }
            val qr = result.getOrNull()
            if (qr == null) {
                status = result.exceptionOrNull()?.message ?: "登录失败"
                continue
            }
            when (qr.state) {
                QrState.CONFIRMED -> {
                    toast("登录成功")
                    return@LaunchedEffect
                }
                QrState.EXPIRED -> {
                    status = "二维码已过期"
                    stopped = true
                    return@LaunchedEffect
                }
                QrState.ERROR -> {
                    status = qr.message ?: "登录失败"
                    stopped = true
                    return@LaunchedEffect
                }
                QrState.VERIFY -> {
                    verifying = true
                    status = "网易云要求安全验证：请在手机上按提示完成验证并确认登录。长时间无反应可改用下方官网登录。"
                }
                QrState.SCANNED -> status = (qr.nickname?.takeIf { it.isNotBlank() } ?: "已扫码") + "，请在手机上确认"
                QrState.WAITING -> status = "用网易云音乐 App 扫码"
            }
        }
    }

    SectionCard(title = "登录二维码", subtitle = "打开网易云音乐 App，扫一扫下方二维码") {
        Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
            Surface(
                shape = RoundedCornerShape(24.dp),
                color = Color.White,
                shadowElevation = 4.dp,
                modifier = Modifier.size(232.dp),
            ) {
                AnimatedContent(
                    image,
                    transitionSpec = { (fadeIn(tween(300)) + scaleIn(tween(300), initialScale = 0.9f)) togetherWith fadeOut(tween(150)) },
                    label = "qr",
                ) { bitmap ->
                    Box(Modifier.fillMaxSize().padding(14.dp), contentAlignment = Alignment.Center) {
                        if (bitmap == null) {
                            CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                        } else {
                            Image(
                                bitmap.asImageBitmap(), "登录二维码",
                                Modifier.fillMaxSize().graphicsLayer { alpha = if (stopped) 0.25f else 1f },
                            )
                            if (stopped) {
                                SoftButton("刷新二维码", { round++ }, icon = Icons.Rounded.Refresh)
                            }
                        }
                    }
                }
            }
        }
        AnimatedContent(status, transitionSpec = { fadeIn(tween(220)) togetherWith fadeOut(tween(120)) }, label = "qrStatus") {
            Text(
                it,
                style = MaterialTheme.typography.bodyMedium,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Reveal(verifying) {
            val nav = LocalNav.current
            SoftButton(
                "改用官网登录",
                {
                    nav.officialLogin = { result ->
                        runCatching { graph.session.accept(result) }
                            .onSuccess { toast("已登录：${it.nickname}") }
                            .onFailure { toast(it.message ?: "登录失败") }
                    }
                },
                Modifier.fillMaxWidth(),
                icon = Icons.Rounded.Language,
            )
        }
    }
}

@Composable
private fun CookieLogin(graph: AppGraph) {
    val toast = LocalToast.current
    val scope = rememberCoroutineScope()
    var cookie by rememberSaveable { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    SectionCard(title = "Cookie 登录", subtitle = "在电脑浏览器登录 music.163.com 后，从开发者工具复制整段 Cookie（至少包含 MUSIC_U，最好同时包含 __csrf）。") {
        AppTextField(cookie, { cookie = it }, "Cookie", singleLine = false, minLines = 3, maxLines = 6, placeholder = "MUSIC_U=…; __csrf=…")
        GradientButton(
            if (busy) "验证中…" else "登录",
            {
                busy = true
                scope.launch {
                    runCatching { graph.session.loginWithCookie(cookie) }
                        .onSuccess { toast("已登录：${it.nickname}") }
                        .onFailure { toast(it.message ?: "登录失败") }
                    busy = false
                }
            },
            Modifier.fillMaxWidth(),
            enabled = cookie.isNotBlank(),
            loading = busy,
        )
    }
}

/** 网易云官网登录（网页内完成验证），成功后返回 { profile, cookies }。 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun OfficialLoginDialog(onAccount: (JSONObject) -> Unit, onDismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    var status by remember { mutableStateOf("请在下方网易云官方页面点击登录，并完成所需验证。登录成功后会自动返回。") }
    var progress by remember { mutableIntStateOf(0) }
    var validating by remember { mutableStateOf(false) }
    var attempted by remember { mutableStateOf<String?>(null) }
    var closed by remember { mutableStateOf(false) }

    fun check(force: Boolean) {
        if (closed || validating) return
        val cookie = CookieManager.getInstance().getCookie("https://music.163.com/")
        val token = runCatching { NeteaseAuth.parseCookies(cookie)["MUSIC_U"] }.getOrNull()
        if (token == null) {
            if (force) status = "尚未取得登录状态，请先在下方官方页面完成登录。"
            return
        }
        if (!force && token == attempted) return
        attempted = token
        validating = true
        status = "正在验证账号…"
        scope.launch {
            val result = runCatching { withContext(Dispatchers.IO) { NeteaseAuth.authenticateCookie(cookie) } }
            if (closed) return@launch
            result.onSuccess {
                CookieManager.getInstance().flush()
                onAccount(it)
            }.onFailure {
                validating = false
                status = when (it) {
                    is SocketTimeoutException -> "验证账号超时，请稍后点击下方按钮重试。"
                    else -> it.message ?: "账号验证失败，请完成页面内的验证后重试。"
                }
            }
        }
    }

    LaunchedEffect(Unit) {
        while (true) {
            delay(1500)
            check(false)
        }
    }
    DisposableEffect(Unit) { onDispose { closed = true } }

    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.surface) {
            Column(Modifier.fillMaxSize().statusBarsPadding()) {
                Row(Modifier.fillMaxWidth().padding(start = 20.dp, end = 8.dp, top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("网易云官网登录", style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
                    IconButton(onClick = onDismiss) { Icon(Icons.Rounded.Close, "关闭") }
                }
                AnimatedContent(status, transitionSpec = { fadeIn() togetherWith fadeOut() }, label = "webStatus") {
                    Text(
                        it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(horizontal = 20.dp, vertical = 6.dp),
                    )
                }
                if (progress in 1..99) {
                    LinearProgressIndicator(progress = { progress / 100f }, modifier = Modifier.fillMaxWidth().height(2.dp))
                } else {
                    Spacer(Modifier.height(2.dp))
                }
                AndroidView(
                    modifier = Modifier.weight(1f).fillMaxWidth(),
                    factory = { context ->
                        WebView(context).apply {
                            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
                            settings.javaScriptEnabled = true
                            settings.domStorageEnabled = true
                            settings.allowFileAccess = false
                            settings.allowContentAccess = false
                            settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
                            settings.safeBrowsingEnabled = true
                            settings.useWideViewPort = true
                            settings.loadWithOverviewMode = true
                            settings.builtInZoomControls = true
                            settings.displayZoomControls = false
                            CookieManager.getInstance().setAcceptCookie(true)
                            CookieManager.getInstance().setAcceptThirdPartyCookies(this, true)
                            webChromeClient = object : WebChromeClient() {
                                override fun onProgressChanged(view: WebView, newProgress: Int) {
                                    progress = newProgress
                                }
                            }
                            webViewClient = object : WebViewClient() {
                                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                                    val url: Uri = request.url
                                    val host = url.host
                                    if (url.scheme.equals("https", true) && host != null &&
                                        (host == "163.com" || host.endsWith(".163.com") || host.endsWith(".126.net"))
                                    ) {
                                        return false
                                    }
                                    status = "请使用当前官方网页内的登录与验证方式。"
                                    return true
                                }

                                override fun onPageFinished(view: WebView, url: String?) {
                                    check(false)
                                }
                            }
                            loadUrl("https://music.163.com/m/login")
                        }
                    },
                    onRelease = { web ->
                        web.stopLoading()
                        web.destroy()
                    },
                )
                Box(Modifier.fillMaxWidth().padding(16.dp)) {
                    GradientButton(
                        "已完成登录，验证账号",
                        { check(true) },
                        Modifier.fillMaxWidth(),
                        loading = validating,
                        icon = Icons.Rounded.VerifiedUser,
                    )
                }
            }
        }
    }
}
