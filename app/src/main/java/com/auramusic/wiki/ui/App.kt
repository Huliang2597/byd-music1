package com.auramusic.wiki.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandHorizontally
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkHorizontally
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Album
import androidx.compose.material.icons.outlined.AssignmentTurnedIn
import androidx.compose.material.icons.outlined.AutoStories
import androidx.compose.material.icons.outlined.LibraryMusic
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.rounded.Album
import androidx.compose.material.icons.rounded.AssignmentTurnedIn
import androidx.compose.material.icons.rounded.AutoStories
import androidx.compose.material.icons.rounded.LibraryMusic
import androidx.compose.material.icons.rounded.Person
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Snackbar
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.auramusic.wiki.AppGraph
import com.auramusic.wiki.ui.components.LocalReduceMotion
import com.auramusic.wiki.ui.components.LocalToast
import com.auramusic.wiki.ui.screens.AlbumScreen
import com.auramusic.wiki.ui.screens.ArtistEditorScreen
import com.auramusic.wiki.ui.screens.LoginScreen
import com.auramusic.wiki.ui.screens.MineScreen
import com.auramusic.wiki.ui.screens.OfficialLoginDialog
import com.auramusic.wiki.ui.screens.SongScreen
import com.auramusic.wiki.ui.screens.TaskScreen
import com.auramusic.wiki.ui.screens.WikiScreen
import kotlinx.coroutines.launch
import org.json.JSONObject

enum class Tab(val label: String, val icon: ImageVector, val selectedIcon: ImageVector) {
    ALBUM("专辑", Icons.Outlined.Album, Icons.Rounded.Album),
    SONG("歌曲", Icons.Outlined.LibraryMusic, Icons.Rounded.LibraryMusic),
    TASKS("任务", Icons.Outlined.AssignmentTurnedIn, Icons.Rounded.AssignmentTurnedIn),
    WIKI("百科", Icons.Outlined.AutoStories, Icons.Rounded.AutoStories),
    MINE("我的", Icons.Outlined.Person, Icons.Rounded.Person),
}

/** 跨页面的导航请求与弹层。 */
@Stable
class AppNav(initial: Tab) {
    var tab by mutableStateOf(initial)
    var songRequest by mutableStateOf<Long?>(null)
    var wikiRequest by mutableStateOf<Long?>(null)
    var artistEditor by mutableStateOf(false)
    var artistEditorQuery by mutableStateOf<String?>(null)
    var officialLogin by mutableStateOf<((JSONObject) -> Unit)?>(null)

    fun openSong(id: Long) {
        songRequest = id
        tab = Tab.SONG
    }

    fun openWiki(id: Long) {
        wikiRequest = id
        tab = Tab.WIKI
    }

    fun openArtistEditor(query: String? = null) {
        artistEditorQuery = query
        artistEditor = true
    }
}

val LocalNav = staticCompositionLocalOf<AppNav> { error("no nav") }

@Composable
fun WikiApp() {
    val context = LocalContext.current
    val graph = remember { AppGraph.get(context) }
    val account by graph.session.account.collectAsState()
    val loggedIn = account != null || graph.session.hasCredential
    var savedTab by rememberSaveable { mutableStateOf(if (loggedIn) Tab.ALBUM.name else Tab.WIKI.name) }
    val nav = remember { AppNav(Tab.valueOf(savedTab)) }
    LaunchedEffect(nav.tab) { savedTab = nav.tab.name }
    LaunchedEffect(Unit) { graph.session.refresh() }

    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val toast: (String) -> Unit = remember {
        { message ->
            scope.launch {
                snackbar.currentSnackbarData?.dismiss()
                snackbar.showSnackbar(message)
            }
        }
    }

    val reduceMotion = remember {
        android.provider.Settings.Global.getFloat(context.contentResolver, android.provider.Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    }
    CompositionLocalProvider(LocalToast provides toast, LocalNav provides nav, LocalReduceMotion provides reduceMotion) {
        Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
            Scaffold(
                containerColor = MaterialTheme.colorScheme.background,
                contentWindowInsets = WindowInsets(0, 0, 0, 0),
                bottomBar = { BottomBar(nav.tab) { nav.tab = it } },
                snackbarHost = {
                    SnackbarHost(snackbar) { data ->
                        Snackbar(
                            data,
                            shape = RoundedCornerShape(18.dp),
                            containerColor = MaterialTheme.colorScheme.inverseSurface,
                            contentColor = MaterialTheme.colorScheme.inverseOnSurface,
                        )
                    }
                },
            ) { padding ->
                AnimatedContent(
                    targetState = nav.tab,
                    transitionSpec = {
                        val forward = targetState.ordinal > initialState.ordinal
                        val direction = if (forward) 1 else -1
                        (slideInHorizontally(tween(340, easing = FastOutSlowInEasing)) { it / 6 * direction } + fadeIn(tween(280)))
                            .togetherWith(slideOutHorizontally(tween(300, easing = FastOutSlowInEasing)) { -it / 8 * direction } + fadeOut(tween(200)))
                    },
                    label = "tabs",
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .consumeWindowInsets(padding)
                        .imePadding(),
                ) { tab ->
                    val needsLogin = tab != Tab.WIKI && !loggedIn
                    AnimatedContent(
                        needsLogin,
                        transitionSpec = { fadeIn(tween(300)) togetherWith fadeOut(tween(200)) },
                        label = "auth",
                    ) { guest ->
                        if (guest) {
                            LoginScreen(graph)
                        } else {
                            when (tab) {
                                Tab.ALBUM -> AlbumScreen(graph)
                                Tab.SONG -> SongScreen(graph)
                                Tab.TASKS -> TaskScreen(graph)
                                Tab.WIKI -> WikiScreen(graph)
                                Tab.MINE -> MineScreen(graph)
                            }
                        }
                    }
                }
            }

            AnimatedVisibility(
                nav.artistEditor,
                enter = slideInVertically(spring(dampingRatio = 0.9f, stiffness = Spring.StiffnessMediumLow)) { it / 3 } + fadeIn(tween(220)),
                exit = slideOutVertically(tween(260)) { it / 3 } + fadeOut(tween(200)),
            ) {
                BackHandler { nav.artistEditor = false }
                ArtistEditorScreen(graph, nav.artistEditorQuery) { nav.artistEditor = false }
            }

            nav.officialLogin?.let { consumer ->
                OfficialLoginDialog(
                    onAccount = { result ->
                        consumer(result)
                        nav.officialLogin = null
                    },
                    onDismiss = { nav.officialLogin = null },
                )
            }
        }
    }
}

@Composable
private fun BottomBar(current: Tab, onSelect: (Tab) -> Unit) {
    Box(
        Modifier
            .fillMaxWidth()
            .navigationBarsPadding()
            .padding(horizontal = 14.dp, vertical = 10.dp),
        contentAlignment = Alignment.Center,
    ) {
        Surface(
            shape = RoundedCornerShape(30.dp),
            color = MaterialTheme.colorScheme.surfaceContainerHigh.copy(alpha = 0.97f),
            shadowElevation = 10.dp,
            tonalElevation = 2.dp,
        ) {
            Row(
                Modifier.padding(horizontal = 8.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(2.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Tab.entries.forEach { tab ->
                    NavItem(tab, tab == current) { onSelect(tab) }
                }
            }
        }
    }
}

@Composable
private fun NavItem(tab: Tab, selected: Boolean, onClick: () -> Unit) {
    val interaction = remember { MutableInteractionSource() }
    val background by animateColorAsState(
        if (selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0f),
        tween(260),
        label = "navBg",
    )
    val tint by animateColorAsState(
        if (selected) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant,
        tween(260),
        label = "navTint",
    )
    Row(
        Modifier
            .clip(CircleShape)
            .background(background)
            .clickable(interaction, indication = androidx.compose.material3.ripple(), onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        AnimatedContent(selected, transitionSpec = { fadeIn(tween(180)) togetherWith fadeOut(tween(120)) }, label = "navIcon") { on ->
            Icon(
                if (on) tab.selectedIcon else tab.icon,
                contentDescription = tab.label,
                tint = tint,
                modifier = Modifier.size(24.dp),
            )
        }
        AnimatedVisibility(
            selected,
            enter = expandHorizontally(tween(260, easing = FastOutSlowInEasing)) + fadeIn(tween(200, delayMillis = 60)),
            exit = shrinkHorizontally(tween(260, easing = FastOutSlowInEasing)) + fadeOut(tween(120)),
        ) {
            Row {
                Spacer(Modifier.width(8.dp))
                Text(tab.label, style = MaterialTheme.typography.labelLarge, color = tint)
            }
        }
    }
}

