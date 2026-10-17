package com.auramusic.wiki.ui.screens

import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AudioFile
import androidx.compose.material.icons.rounded.AutoFixHigh
import androidx.compose.material.icons.rounded.AutoStories
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.MusicNote
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.rounded.WarningAmber
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.auramusic.wiki.AppGraph
import com.auramusic.wiki.data.NosFile
import com.auramusic.wiki.data.PublicWiki
import com.auramusic.wiki.data.SongDetail
import com.auramusic.wiki.data.SongHit
import com.auramusic.wiki.data.UploadKind
import com.auramusic.wiki.data.WikiApi
import com.auramusic.wiki.data.WikiArtist
import com.auramusic.wiki.ui.LocalNav
import com.auramusic.wiki.ui.components.AppTextField
import com.auramusic.wiki.ui.components.ArtistPickerSheet
import com.auramusic.wiki.ui.components.DatePickerSheet
import com.auramusic.wiki.ui.components.EmptyState
import com.auramusic.wiki.ui.components.ErrorState
import com.auramusic.wiki.ui.components.FlowRowCompat
import com.auramusic.wiki.ui.components.GradientButton
import com.auramusic.wiki.ui.components.GradientProgress
import com.auramusic.wiki.ui.components.Hint
import com.auramusic.wiki.ui.components.LanguagePickerSheet
import com.auramusic.wiki.ui.components.LinesEditorSheet
import com.auramusic.wiki.ui.components.LocalToast
import com.auramusic.wiki.ui.components.PageHeader
import com.auramusic.wiki.ui.components.Reveal
import com.auramusic.wiki.ui.components.SectionCard
import com.auramusic.wiki.ui.components.SelectorField
import com.auramusic.wiki.ui.components.SkeletonList
import com.auramusic.wiki.ui.components.SoftButton
import com.auramusic.wiki.ui.components.enterAnimation
import com.auramusic.wiki.ui.theme.LocalBrand
import com.auramusic.wiki.ui.theme.MonoStyle
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import org.json.JSONObject

/** 可编辑的歌曲资料。 */
class SongEdit(val detail: SongDetail) {
    var name by mutableStateOf(detail.name)
    var subtitles by mutableStateOf(detail.subTitle.split(';').map { it.trim() }.filter { it.isNotEmpty() })
    var transName by mutableStateOf(detail.transName)
    var publishTime by mutableStateOf(detail.publishTime.takeIf { it > 0 })
    var languages by mutableStateOf(detail.language.split(',').map { it.trim() }.filter { it.isNotEmpty() })
    var originalCover by mutableStateOf(detail.originalCover)
    var artists by mutableStateOf(detail.artists)
    var lyricArtists by mutableStateOf(detail.lyricArtists)
    var composeArtists by mutableStateOf(detail.composeArtists)
    var arrangeArtists by mutableStateOf(detail.arrangeArtists)
    var lyric by mutableStateOf(detail.lyric)
    var transLyric by mutableStateOf(detail.transLyric)
    var source by mutableStateOf("")
    var notes by mutableStateOf("")
    var audioError by mutableStateOf<Int?>(null)
    var audio by mutableStateOf<NosFile?>(null)
    var audioProgress by mutableFloatStateOf(0f)
    var audioUploading by mutableStateOf(false)
    var audioMessage by mutableStateOf<String?>(null)

    private fun ids(list: List<WikiArtist>) = list.map { it.id }

    /** 只包含有变化的字段。 */
    fun change(): JSONObject {
        val d = detail
        val json = JSONObject().put("songId", d.id)
        if (name != d.name) json.put("songName", name.trim())
        subtitles.joinToString(";").let { if (it != d.subTitle) json.put("songSubTitle", it) }
        if (transName != d.transName) json.put("transName", transName.trim())
        publishTime?.let { if (it != d.publishTime) json.put("publishTime", it) }
        languages.joinToString(",").let { if (it != d.language) json.put("language", it) }
        if (originalCover != d.originalCover && originalCover != 0) json.put("originalCover", originalCover)
        if (ids(artists) != ids(d.artists)) json.put("artistSimpleVos", WikiApi.artistsJson(artists))
        if (ids(lyricArtists) != ids(d.lyricArtists)) json.put("lyricArtists", WikiApi.artistsJson(lyricArtists))
        if (ids(composeArtists) != ids(d.composeArtists)) json.put("composeArtists", WikiApi.artistsJson(composeArtists))
        if (ids(arrangeArtists) != ids(d.arrangeArtists)) json.put("arrangeArtists", WikiApi.artistsJson(arrangeArtists))
        if (lyric != d.lyric) json.put("lyricContent", lyric)
        if (transLyric != d.transLyric) json.put("transLyricContent", transLyric)
        audio?.let { file ->
            val music = file.toJson().put("songId", d.id)
            audioError?.let { music.put("errorType", it) }
            json.put("songMusicVo", music)
        }
        return json
    }
}

private val STAMP = Regex("^\\[([0-9.:]+)]")

private fun stamps(lyric: String): List<String> =
    lyric.lines().mapNotNull { STAMP.find(it.trim())?.groupValues?.get(1) }

class SongViewModel(private val graph: AppGraph) : ViewModel() {
    var query by mutableStateOf("")
    var searching by mutableStateOf(false)
    var hits by mutableStateOf<List<SongHit>?>(null)
    var searchError by mutableStateOf<String?>(null)

    var songId by mutableStateOf<Long?>(null)
    var edit by mutableStateOf<SongEdit?>(null)
    var loadError by mutableStateOf<String?>(null)
    var privileges by mutableStateOf<Map<Int, Boolean>>(emptyMap())
    var submitting by mutableStateOf(false)
    var submitted by mutableStateOf(false)
    val failures = mutableStateListOf<String>()
    private var loadJob: Job? = null
    private var uploadJob: Job? = null

    fun editable(fixType: Int) = privileges[fixType] ?: true

    suspend fun searchArtists(keyword: String): List<WikiArtist> = graph.api.searchArtists(keyword)

    fun search(onToast: (String) -> Unit) {
        val text = query.trim()
        if (text.isEmpty()) return
        val id = PublicWiki.normalizeId(text)
        if (id != null && PublicWiki.shortLink(text) == null) {
            open(id.toLong())
            return
        }
        searching = true
        searchError = null
        viewModelScope.launch {
            try {
                if (PublicWiki.shortLink(text) != null) {
                    open(PublicWiki.resolveId(text).toLong())
                } else {
                    hits = graph.api.searchSongs(text)
                }
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                searchError = e.message ?: "加载失败"
                onToast(searchError.orEmpty())
            } finally {
                searching = false
            }
        }
    }

    fun open(id: Long) {
        songId = id
        reload()
    }

    fun reload() {
        val id = songId ?: return
        loadJob?.cancel()
        uploadJob?.cancel()
        edit = null
        loadError = null
        privileges = emptyMap()
        failures.clear()
        submitted = false
        loadJob = viewModelScope.launch {
            try {
                edit = SongEdit(graph.api.song(id))
                privileges = runCatching { graph.api.privileges(3, id) }.getOrDefault(emptyMap())
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                loadError = e.message ?: "加载失败"
            }
        }
    }

    fun close() {
        loadJob?.cancel()
        uploadJob?.cancel()
        songId = null
        edit = null
        loadError = null
    }

    fun uploadAudio(uri: Uri) {
        val state = edit ?: return
        uploadJob?.cancel()
        state.audio = null
        state.audioMessage = null
        state.audioProgress = 0f
        state.audioUploading = true
        uploadJob = viewModelScope.launch {
            try {
                state.audio = graph.uploader.upload(uri, UploadKind.AUDIO) { state.audioProgress = it }
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                state.audioMessage = e.message ?: "上传失败"
            } finally {
                state.audioUploading = false
            }
        }
    }

    fun submit(onToast: (String) -> Unit) {
        val state = edit ?: return
        if (submitting) return
        submitting = true
        failures.clear()
        viewModelScope.launch {
            val message = runCatching { validateAndSend(state) }.getOrElse { it.message ?: "提交失败" }
            submitting = false
            if (message == null) submitted = true else onToast(message)
        }
    }

    /** 校验歌词并提交，返回错误提示；成功返回 null。 */
    private suspend fun validateAndSend(state: SongEdit): String? {
        val change = state.change()
        if (state.audioError != null && state.audio == null) return "请上传完成音频后再提交"
        val lyric = if (change.has("lyricContent")) change.optString("lyricContent") else null
        val trans = if (change.has("transLyricContent")) change.optString("transLyricContent") else null
        if (!trans.isNullOrBlank() && state.lyric.isBlank()) return "需要提交原文歌词才可提交翻译歌词哦"
        val duration = state.detail.durationMs
        if (!lyric.isNullOrBlank()) {
            val check = graph.api.checkLyric("lrc", lyric, duration)
            failures.addAll(check.failures.map { "原歌词：$it" })
            if (!check.ok) return check.message.ifBlank { "歌词存在错误，请检查" }
        }
        if (!trans.isNullOrBlank()) {
            val check = graph.api.checkLyric("trans", trans, duration, trans)
            failures.addAll(check.failures.map { "翻译歌词：$it" })
            if (!check.ok) {
                return if (stamps(state.lyric) != stamps(trans)) "翻译歌词时间轴必须与原文歌词时间轴一一对应且保持一样哦"
                else check.message.ifBlank { "歌词存在错误，请检查" }
            }
        }
        if (change.length() <= 1) return "请填写信息"
        if (state.source.isBlank()) return "资料来源必填"
        change.put("source", state.source.trim()).put("notes", state.notes.trim())
        graph.api.updateSong(change)
        return null
    }
}

@Composable
fun SongScreen(graph: AppGraph) {
    val vm: SongViewModel = viewModel { SongViewModel(graph) }
    val nav = LocalNav.current
    LaunchedEffect(nav.songRequest) {
        nav.songRequest?.let {
            vm.open(it)
            nav.songRequest = null
        }
    }
    BackHandler(enabled = vm.songId != null) { vm.close() }
    AnimatedContent(
        vm.songId,
        transitionSpec = {
            val forward = targetState != null
            val dir = if (forward) 1 else -1
            (slideInHorizontally(tween(360, easing = FastOutSlowInEasing)) { it / 3 * dir } + fadeIn(tween(300)))
                .togetherWith(slideOutHorizontally(tween(300, easing = FastOutSlowInEasing)) { -it / 4 * dir } + fadeOut(tween(200)))
        },
        label = "songNav",
    ) { id ->
        if (id == null) SongSearch(vm) else SongEditor(vm, id)
    }
}

@Composable
private fun SongSearch(vm: SongViewModel) {
    val toast = LocalToast.current
    val focus = LocalFocusManager.current
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
        item(key = "header") {
            Box(Modifier.statusBarsPadding()) { PageHeader("歌曲资料共创", "补充或修改歌曲名、作词作曲、歌词与翻译，或报告并替换错误的音频。") }
        }
        item(key = "search") {
            SectionCard(
                "找到要完善的歌曲",
                Modifier.padding(horizontal = 16.dp).enterAnimation(0),
                subtitle = "也可以从任务中心领取任务，直接跳转到这里编辑。",
            ) {
                AppTextField(
                    vm.query, { vm.query = it }, "歌名、歌曲 ID 或分享链接",
                    leading = Icons.Rounded.Search,
                    imeAction = ImeAction.Search,
                    onIme = { focus.clearFocus(); vm.search(toast) },
                )
                GradientButton("搜索", { focus.clearFocus(); vm.search(toast) }, Modifier.fillMaxWidth(), loading = vm.searching, icon = Icons.Rounded.Search)
            }
        }
        val hits = vm.hits
        when {
            vm.searching && hits == null -> item(key = "loading") { SkeletonList(5, Modifier.padding(16.dp)) }
            hits == null -> item(key = "empty") { EmptyState("输入歌名或粘贴分享链接开始", Modifier.padding(16.dp), Icons.Rounded.MusicNote) }
            hits.isEmpty() -> item(key = "none") { EmptyState("没有找到相关歌曲", Modifier.padding(16.dp)) }
            else -> itemsIndexed(hits, key = { _, h -> h.id }) { index, hit ->
                Row(
                    Modifier
                        .animateItem()
                        .padding(horizontal = 16.dp, vertical = 5.dp)
                        .enterAnimation(index, hit.id)
                        .fillMaxWidth()
                        .clip(MaterialTheme.shapes.large)
                        .background(MaterialTheme.colorScheme.surfaceContainerLow)
                        .clickable { vm.open(hit.id) }
                        .padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(
                        Modifier.size(44.dp).clip(RoundedCornerShape(14.dp)).background(LocalBrand.current.gradient),
                        contentAlignment = Alignment.Center,
                    ) { Icon(Icons.Rounded.MusicNote, null, tint = androidx.compose.ui.graphics.Color.White) }
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Text(hit.name, style = MaterialTheme.typography.titleSmall, maxLines = 1)
                        Text(hit.subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                    }
                    Text("ID ${hit.id}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

private enum class Picker { NONE, SUBTITLE, LANGUAGE, DATE, ARTIST, LYRICIST, COMPOSER, ARRANGER }

@Composable
private fun SongEditor(vm: SongViewModel, id: Long) {
    val nav = LocalNav.current
    val toast = LocalToast.current
    val edit = vm.edit
    var picker by remember { mutableStateOf(Picker.NONE) }
    val audioPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri -> uri?.let(vm::uploadAudio) }

    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item(key = "header") {
            Box(Modifier.statusBarsPadding()) {
                PageHeader("歌曲 $id", edit?.detail?.let { "${it.name} · ${it.albumName}" }, onBack = { vm.close() })
            }
        }
        item(key = "wiki") {
            SoftButton("查看歌曲百科与贡献", { nav.openWiki(id) }, Modifier.fillMaxWidth(), icon = Icons.Rounded.AutoStories)
        }
        if (edit == null) {
            item(key = "state") {
                if (vm.loadError != null) ErrorState(vm.loadError.orEmpty(), { vm.reload() }) else SkeletonList(4)
            }
            return@LazyColumn
        }
        item(key = "basic") {
            SectionCard("歌曲基本信息", Modifier.enterAnimation(0)) {
                AppTextField(edit.name, { edit.name = it }, "歌曲名", enabled = vm.editable(1))
                SelectorField("副标题", edit.subtitles, { picker = Picker.SUBTITLE }, enabled = vm.editable(2), placeholder = "暂无",
                    onRemove = { i -> edit.subtitles = edit.subtitles.filterIndexed { j, _ -> j != i } })
                AppTextField(edit.transName, { edit.transName = it }, "翻译名", enabled = vm.editable(10))
                AppTextField(edit.detail.company, {}, "发行公司", enabled = false)
                SelectorField(
                    "发行时间",
                    listOfNotNull(edit.publishTime?.let { SimpleDateFormat("yyyy-MM-dd", Locale.CHINA).format(Date(it)) }),
                    { picker = Picker.DATE },
                    enabled = vm.editable(6),
                    placeholder = "选择日期",
                )
                SelectorField("语种", edit.languages, { picker = Picker.LANGUAGE }, enabled = vm.editable(4),
                    onRemove = { i -> edit.languages = edit.languages.filterIndexed { j, _ -> j != i } })
                Text("原/翻唱", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                FlowRowCompat {
                    listOf(1 to "原唱", 2 to "翻唱", 3 to "其他").forEach { (value, label) ->
                        FilterChip(
                            selected = edit.originalCover == value,
                            onClick = { edit.originalCover = value },
                            enabled = vm.editable(24),
                            label = { Text(label) },
                        )
                    }
                }
            }
        }
        item(key = "creators") {
            SectionCard("创作者团队信息", Modifier.enterAnimation(1), subtitle = "新艺人可以直接输入名字添加") {
                ArtistSelector("艺人", edit.artists, vm.editable(5), { picker = Picker.ARTIST }) { edit.artists = it }
                ArtistSelector("作词", edit.lyricArtists, vm.editable(7), { picker = Picker.LYRICIST }) { edit.lyricArtists = it }
                ArtistSelector("作曲", edit.composeArtists, vm.editable(8), { picker = Picker.COMPOSER }) { edit.composeArtists = it }
                ArtistSelector("编曲", edit.arrangeArtists, vm.editable(9), { picker = Picker.ARRANGER }) { edit.arrangeArtists = it }
            }
        }
        item(key = "lyric") {
            val lyricEditable = vm.editable(21) && !edit.detail.lyricLocked
            val transEditable = vm.editable(22) && !edit.detail.transLyricLocked
            SectionCard(
                "歌词",
                Modifier.enterAnimation(2),
                subtitle = "带时间轴的歌词（LRC，每行 [mm:ss.xx]歌词）获 50 积分起，翻译获 200 积分。翻译的时间轴必须与原文逐行一致。",
            ) {
                if (edit.detail.lyricLocked || edit.detail.transLyricLocked) {
                    Notice(Icons.Rounded.Lock, "歌词已锁定")
                } else if (!lyricEditable && !transEditable) {
                    Notice(Icons.Rounded.Lock, "当前账号不能提交歌词")
                }
                AppTextField(edit.lyric, { edit.lyric = it }, "原文歌词（LRC）", singleLine = false, minLines = 5, maxLines = 14, enabled = lyricEditable, textStyle = MonoStyle)
                AppTextField(edit.transLyric, { edit.transLyric = it }, "翻译歌词（LRC）", singleLine = false, minLines = 5, maxLines = 14, enabled = transEditable, textStyle = MonoStyle)
                SoftButton(
                    "按原文时间轴生成翻译模板",
                    {
                        val existing = edit.transLyric.lines().mapNotNull { line ->
                            STAMP.find(line.trim())?.let { it.groupValues[1] to line.trim().substring(it.value.length) }
                        }.toMap()
                        edit.transLyric = stamps(edit.lyric).joinToString("\n") { "[$it]" + existing[it].orEmpty() }
                    },
                    Modifier.fillMaxWidth(),
                    enabled = transEditable && stamps(edit.lyric).isNotEmpty(),
                    icon = Icons.Rounded.AutoFixHigh,
                )
            }
        }
        item(key = "audio") {
            val audioEditable = vm.editable(3)
            SectionCard("音频", Modifier.enterAnimation(3), subtitle = "如果现有音频有问题，选择原因并上传正确的音频。") {
                FlowRowCompat {
                    WikiApi.AUDIO_ERRORS.forEach { (value, label) ->
                        FilterChip(
                            selected = edit.audioError == value,
                            onClick = { edit.audioError = if (edit.audioError == value) null else value },
                            enabled = audioEditable,
                            label = { Text(label) },
                        )
                    }
                }
                Reveal(edit.audioError != null) {
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        SoftButton(
                            if (edit.audio == null && !edit.audioUploading) "上传新音频" else "重新选择音频",
                            { audioPicker.launch("audio/*") },
                            Modifier.fillMaxWidth(),
                            enabled = audioEditable,
                            icon = Icons.Rounded.AudioFile,
                        )
                        Reveal(edit.audioUploading) {
                            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                GradientProgress(edit.audioProgress)
                                Hint("上传中 ${(edit.audioProgress * 100).toInt()}%")
                            }
                        }
                        edit.audio?.let { Notice(Icons.Rounded.CheckCircle, "已上传：${it.fileName}", success = true) }
                        edit.audioMessage?.let { Notice(Icons.Rounded.WarningAmber, it, danger = true) }
                    }
                }
            }
        }
        item(key = "submit") {
            SectionCard("修订日志", Modifier.enterAnimation(4)) {
                AppTextField(edit.source, { edit.source = it }, "资料来源", required = true, singleLine = false, minLines = 2, supporting = "资料来源的详细参考网址")
                AppTextField(edit.notes, { edit.notes = it }, "补充备注", singleLine = false, minLines = 2, supporting = "只会被审核人员看到")
                Reveal(vm.failures.isNotEmpty()) {
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(14.dp))
                            .background(MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.5f))
                            .padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        vm.failures.forEach { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onErrorContainer) }
                    }
                }
                GradientButton(
                    if (vm.submitting) "提交中…" else "提交审核",
                    { vm.submit(toast) },
                    Modifier.fillMaxWidth(),
                    loading = vm.submitting,
                    icon = Icons.AutoMirrored.Rounded.Send,
                )
            }
        }
    }

    if (edit != null) {
        when (picker) {
            Picker.SUBTITLE -> LinesEditorSheet("副标题", "每行一个，例：游戏《xx》原声集", edit.subtitles, { edit.subtitles = it; picker = Picker.NONE }) { picker = Picker.NONE }
            Picker.LANGUAGE -> LanguagePickerSheet(WikiApi.LANGUAGES, WikiApi.EXCLUSIVE_LANGUAGES, edit.languages, { edit.languages = it; picker = Picker.NONE }) { picker = Picker.NONE }
            Picker.DATE -> DatePickerSheet(edit.publishTime, { edit.publishTime = it }) { picker = Picker.NONE }
            Picker.ARTIST, Picker.LYRICIST, Picker.COMPOSER, Picker.ARRANGER -> {
                ArtistPickerSheet(
                    search = vm::searchArtists,
                    onPick = { artist ->
                        when (picker) {
                            Picker.ARTIST -> edit.artists = edit.artists + artist
                            Picker.LYRICIST -> edit.lyricArtists = edit.lyricArtists + artist
                            Picker.COMPOSER -> edit.composeArtists = edit.composeArtists + artist
                            else -> edit.arrangeArtists = edit.arrangeArtists + artist
                        }
                        picker = Picker.NONE
                    },
                    onDismiss = { picker = Picker.NONE },
                )
            }
            Picker.NONE -> Unit
        }
    }

    if (vm.submitted) {
        AlertDialog(
            onDismissRequest = { vm.submitted = false; vm.close() },
            icon = { Icon(Icons.Rounded.CheckCircle, null, tint = LocalBrand.current.success) },
            title = { Text("已提交") },
            text = { Text("修改已提交审核，可在「我的 → 我的贡献 → 歌曲」查看进度。") },
            confirmButton = { TextButton(onClick = { vm.submitted = false; vm.close() }) { Text("好的") } },
        )
    }
}

@Composable
fun ArtistSelector(label: String, artists: List<WikiArtist>, enabled: Boolean, onAdd: () -> Unit, onChange: (List<WikiArtist>) -> Unit) {
    SelectorField(
        label,
        artists.map { if (it.id == null) "${it.name}（新）" else it.name },
        onAdd,
        enabled = enabled,
        placeholder = "点击添加",
        onRemove = { i -> onChange(artists.filterIndexed { j, _ -> j != i }) },
    )
}

@Composable
fun Notice(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String, success: Boolean = false, danger: Boolean = false) {
    val color = when {
        success -> LocalBrand.current.success
        danger -> MaterialTheme.colorScheme.error
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(color.copy(alpha = 0.1f))
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, Modifier.size(18.dp), tint = color)
        Spacer(Modifier.width(8.dp))
        Text(text, style = MaterialTheme.typography.bodySmall, color = color)
    }
}
