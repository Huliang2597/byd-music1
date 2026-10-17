package com.auramusic.wiki

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStore
import androidx.lifecycle.ViewModelStoreOwner
import androidx.lifecycle.viewmodel.compose.LocalViewModelStoreOwner
import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import com.android.resources.NightMode
import com.auramusic.wiki.data.ArtistDetail
import com.auramusic.wiki.data.Contribution
import com.auramusic.wiki.data.Devote
import com.auramusic.wiki.data.NosFile
import com.auramusic.wiki.data.Page
import com.auramusic.wiki.data.Recommend
import com.auramusic.wiki.data.SongDetail
import com.auramusic.wiki.data.TaskGroup
import com.auramusic.wiki.data.TaskItem
import com.auramusic.wiki.data.WikiArtist
import com.auramusic.wiki.ui.AppNav
import com.auramusic.wiki.ui.LocalNav
import com.auramusic.wiki.ui.Tab
import com.auramusic.wiki.ui.components.LocalReduceMotion
import com.auramusic.wiki.ui.screens.AlbumScreen
import com.auramusic.wiki.ui.screens.AlbumSong
import com.auramusic.wiki.ui.screens.AlbumViewModel
import com.auramusic.wiki.ui.screens.LoginScreen
import com.auramusic.wiki.ui.screens.MineScreen
import com.auramusic.wiki.ui.screens.MineViewModel
import com.auramusic.wiki.ui.screens.SongEdit
import com.auramusic.wiki.ui.screens.SongScreen
import com.auramusic.wiki.ui.screens.SongViewModel
import com.auramusic.wiki.ui.screens.TaskScreen
import com.auramusic.wiki.ui.screens.TaskViewModel
import com.auramusic.wiki.ui.screens.WikiScreen
import com.auramusic.wiki.ui.screens.WikiViewModel
import com.auramusic.wiki.ui.theme.WikiTheme
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test

class ScreenshotTest {
    @get:Rule
    val paparazzi = Paparazzi(deviceConfig = DeviceConfig.PIXEL_6.copy(softButtons = false), maxPercentDifference = 1.0)

    private val owner = object : ViewModelStoreOwner {
        override val viewModelStore = ViewModelStore()
    }

    private val registryOwner = object : androidx.activity.result.ActivityResultRegistryOwner {
        override val activityResultRegistry = object : androidx.activity.result.ActivityResultRegistry() {
            override fun <I, O> onLaunch(
                requestCode: Int,
                contract: androidx.activity.result.contract.ActivityResultContract<I, O>,
                input: I,
                options: androidx.core.app.ActivityOptionsCompat?,
            ) = Unit
        }
    }

    private inline fun <reified T : ViewModel> prepare(crossinline create: () -> T): T =
        ViewModelProvider(owner, object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <V : ViewModel> create(modelClass: Class<V>): V = create() as V
        })[T::class.java]

    private fun graph() = AppGraph.get(FakeContext(paparazzi.context))

    @Composable
    private fun Frame(dark: Boolean = false, content: @Composable () -> Unit) {
        CompositionLocalProvider(LocalViewModelStoreOwner provides owner, LocalNav provides AppNav(Tab.WIKI), LocalReduceMotion provides true, androidx.activity.compose.LocalActivityResultRegistryOwner provides registryOwner) {
            WikiTheme(dark = dark) {
                Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) { content() }
            }
        }
    }

    @Test
    fun appShell() {
        graph()
        paparazzi.snapshot {
            CompositionLocalProvider(
                LocalViewModelStoreOwner provides owner,
                androidx.activity.compose.LocalActivityResultRegistryOwner provides registryOwner,
                androidx.compose.ui.platform.LocalContext provides FakeContext(paparazzi.context),
            ) {
                WikiTheme { com.auramusic.wiki.ui.WikiApp() }
            }
        }
    }

    @Test
    fun login() {
        val graph = graph()
        paparazzi.snapshot { Frame { LoginScreen(graph) } }
    }

    @Test
    fun loginDark() {
        val graph = graph()
        paparazzi.unsafeUpdateConfig(DeviceConfig.PIXEL_6.copy(softButtons = false, nightMode = NightMode.NIGHT))
        paparazzi.snapshot { Frame(dark = true) { LoginScreen(graph) } }
    }

    @Test
    fun wiki() {
        val graph = graph()
        val vm = prepare { WikiViewModel(graph) }
        vm.input = "1901371647"
        vm.status = "查询完成 · ID 1901371647"
        vm.history = listOf("1901371647" to "晴天", "186016" to "七里香", "5257138" to "夜曲")
        vm.result = JSONObject().put(
            "data",
            JSONObject()
                .put("songId", "1901371647").put("songName", "晴天").put("artistName", JSONArray(listOf("周杰伦")))
                .put("wiki", JSONObject().put("language", "国语").put("bpm", "69").put("releaseDate", "2003-07-31")
                    .put("genres", JSONArray(listOf("流行", "抒情")))
                    .put("creators", JSONArray().put(JSONObject().put("role", "作词").put("people", JSONArray().put(JSONObject().put("name", "周杰伦").put("artistId", "6452"))))
                        .put(JSONObject().put("role", "编曲").put("people", JSONArray().put(JSONObject().put("name", "林迈可"))))))
                .put("ugc", JSONObject().put("duration", "04:29").put("coverType", "原唱"))
                .put("records", JSONArray().put(JSONObject().put("nickName", "云村小编").put("userId", "12345").put("createTime", 1700000000000).put("approveNames", JSONArray(listOf("歌词", "翻译")))))
        )
        paparazzi.snapshot { Frame { WikiScreen(graph) } }
    }

    private fun song() = SongDetail(
        id = 186016, name = "七里香", subTitle = "", transName = "Common Jasmin Orange", company = "杰威尔音乐",
        publishTime = 1091289600000, language = "国语", originalCover = 1,
        artists = listOf(WikiArtist(6452, "周杰伦")), lyricArtists = listOf(WikiArtist(null, "方文山")),
        composeArtists = listOf(WikiArtist(6452, "周杰伦")), arrangeArtists = listOf(WikiArtist(null, "钟兴民")),
        albumName = "七里香", lyric = "[00:21.00]窗外的麻雀\n[00:24.50]在电线杆上多嘴", transLyric = "",
        durationMs = 299000, playUrl = null, lyricLocked = false, transLyricLocked = false,
    )

    @Test
    fun songEditor() {
        val graph = graph()
        val vm = prepare { SongViewModel(graph) }
        vm.songId = 186016
        vm.edit = SongEdit(song()).apply { audioError = 2; audioUploading = true; audioProgress = 0.46f }
        paparazzi.unsafeUpdateConfig(DeviceConfig.PIXEL_6.copy(softButtons = false, screenHeight = 5200))
        paparazzi.snapshot { Frame { SongScreen(graph) } }
    }

    @Test
    fun album() {
        val graph = graph()
        val vm = prepare { AlbumViewModel(graph) }
        vm.artist = ArtistDetail(6452, "周杰伦", null)
        vm.albumArtists = listOf(WikiArtist(6452, "周杰伦"))
        vm.albumName = "最伟大的作品"
        vm.company = "杰威尔音乐"
        vm.publishTime = 1657814400000
        vm.languages = listOf("国语")
        val done = AlbumSong("最伟大的作品.flac", vm.albumArtists, vm.languages, emptyList())
        done.file = NosFile("最伟大的作品.flac", 1, "audio/flac", "ymusic", "k", "", "", "")
        val uploading = AlbumSong("还在流浪.mp3", vm.albumArtists, vm.languages, emptyList()).apply { progress = 0.62f; expanded = true }
        vm.songs.add(done)
        vm.songs.add(uploading)
        paparazzi.unsafeUpdateConfig(DeviceConfig.PIXEL_6.copy(softButtons = false, screenHeight = 6400))
        paparazzi.snapshot { Frame { AlbumScreen(graph) } }
    }

    @Test
    fun tasks() {
        val graph = graph()
        val vm = prepare { TaskViewModel(graph) }
        val group = TaskGroup(1, "华语经典歌曲歌词补全", null, null, 1280, 356)
        vm.recommend.data = listOf(
            Recommend(group, 3, listOf(
                TaskItem(1, "晴天", "周杰伦", 1, 3, "50", "9.8w", 0, 1760000000000, ""),
                TaskItem(2, "稻香", "周杰伦", 1, 3, "50", "7.1w", null, null, ""),
            )),
        )
        paparazzi.snapshot { Frame { TaskScreen(graph) } }
    }

    @Test
    fun mine() {
        val graph = graph()
        val vm = prepare { MineViewModel(graph) }
        vm.devote = Devote(128, 3560)
        vm.list = Page(
            listOf(
                Contribution("七里香", 1, 1700000000000, 5, "周杰伦", listOf("歌词", "翻译"), emptyList()),
                Contribution("最伟大的作品", 2, 1700100000000, 1, "周杰伦", emptyList(), emptyList()),
                Contribution("夜曲", 3, 1700200000000, -5, "周杰伦", emptyList(), listOf("音频")),
            ),
            23,
        )
        paparazzi.unsafeUpdateConfig(DeviceConfig.PIXEL_6.copy(softButtons = false, screenHeight = 3600))
        paparazzi.snapshot { Frame { MineScreen(graph) } }
    }
}
