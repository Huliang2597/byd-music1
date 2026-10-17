package com.auramusic.wiki.ui.screens

import android.graphics.Bitmap
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AddPhotoAlternate
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.ExpandMore
import androidx.compose.material.icons.rounded.LibraryAdd
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.rounded.SwapHoriz
import androidx.compose.material.icons.rounded.WarningAmber
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.auramusic.wiki.AppGraph
import com.auramusic.wiki.ui.LocalBottomBarSpace
import com.auramusic.wiki.data.ArtistDetail
import com.auramusic.wiki.data.Images
import com.auramusic.wiki.data.Links
import com.auramusic.wiki.data.NosFile
import com.auramusic.wiki.data.UploadKind
import com.auramusic.wiki.data.WikiApi
import com.auramusic.wiki.data.WikiArtist
import com.auramusic.wiki.data.WikiTag
import com.auramusic.wiki.ui.components.AppTextField
import com.auramusic.wiki.ui.components.ArtistPickerSheet
import com.auramusic.wiki.ui.components.DatePickerSheet
import com.auramusic.wiki.ui.components.EmptyState
import com.auramusic.wiki.ui.components.FlowRowCompat
import com.auramusic.wiki.ui.components.GradientButton
import com.auramusic.wiki.ui.components.GradientProgress
import com.auramusic.wiki.ui.components.Hint
import com.auramusic.wiki.ui.components.LanguagePickerSheet
import com.auramusic.wiki.ui.components.LinesEditorSheet
import com.auramusic.wiki.ui.components.LocalToast
import com.auramusic.wiki.ui.components.PageHeader
import com.auramusic.wiki.ui.components.RemoteImage
import com.auramusic.wiki.ui.components.Reveal
import com.auramusic.wiki.ui.components.SectionCard
import com.auramusic.wiki.ui.components.SelectorField
import com.auramusic.wiki.ui.components.SoftButton
import com.auramusic.wiki.ui.components.TagPickerSheet
import com.auramusic.wiki.ui.components.enterAnimation
import com.auramusic.wiki.ui.theme.LocalBrand
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

class AlbumSong(val fileName: String, artists: List<WikiArtist>, languages: List<String>, tags: List<WikiTag>) {
    val key: String = UUID.randomUUID().toString()
    val songFId: String = UUID.randomUUID().toString().replace("-", "").take(10)
    var name by mutableStateOf(fileName.substringBeforeLast('.'))
    var subtitles by mutableStateOf<List<String>>(emptyList())
    var transName by mutableStateOf("")
    var artists by mutableStateOf(artists)
    var languages by mutableStateOf(languages)
    var tags by mutableStateOf(tags)
    var disc by mutableIntStateOf(1)
    var progress by mutableFloatStateOf(0f)
    var file by mutableStateOf<NosFile?>(null)
    var error by mutableStateOf<String?>(null)
    var expanded by mutableStateOf(false)
    var uri: Uri? = null
    var job: Job? = null
}

class AlbumViewModel(private val graph: AppGraph) : ViewModel() {
    var artistInput by mutableStateOf("")
    var artistError by mutableStateOf<String?>(null)
    var artistLoading by mutableStateOf(false)
    var artist by mutableStateOf<ArtistDetail?>(null)
    var albumName by mutableStateOf("")
    var subtitles by mutableStateOf<List<String>>(emptyList())
    var albumType by mutableStateOf("专辑")
    var transName by mutableStateOf("")
    var albumArtists by mutableStateOf<List<WikiArtist>>(emptyList())
    var company by mutableStateOf("")
    var publishTime by mutableStateOf<Long?>(null)
    var languages by mutableStateOf<List<String>>(emptyList())
    var tags by mutableStateOf<List<WikiTag>>(emptyList())
    var production by mutableStateOf("")
    var source by mutableStateOf("")
    var notes by mutableStateOf("")
    var agreed by mutableStateOf(false)
    val songs = mutableStateListOf<AlbumSong>()
    var coverPreview by mutableStateOf<Bitmap?>(null)
    var coverProgress by mutableFloatStateOf(0f)
    var coverRaw by mutableStateOf<NosFile?>(null)
    var coverSquare by mutableStateOf<NosFile?>(null)
    var coverError by mutableStateOf<String?>(null)
    var submitting by mutableStateOf(false)
    var submitted by mutableStateOf(false)
    private var coverJob: Job? = null

    suspend fun searchArtists(keyword: String) = graph.api.searchArtists(keyword)
    suspend fun searchTags(keyword: String) = graph.api.tags(keyword)

    fun confirmArtistInput() {
        val id = Links.parseArtistId(artistInput)
        if (id == null) {
            artistError = "没有识别到艺人 ID"
            return
        }
        loadArtist(id)
    }

    fun loadArtist(id: Long) {
        artistError = null
        artistLoading = true
        viewModelScope.launch {
            try {
                val detail = graph.api.artist(id)
                artist = detail
                if (albumArtists.isEmpty()) albumArtists = listOf(WikiArtist(detail.id, detail.name, detail.avatarUrl))
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                artistError = e.message ?: "加载失败"
            } finally {
                artistLoading = false
            }
        }
    }

    fun addAudio(uris: List<Uri>) {
        for (uri in uris) {
            val song = AlbumSong(graph.uploader.displayName(uri), albumArtists, languages, tags)
            song.uri = uri
            songs.add(song)
            upload(song)
        }
    }

    fun upload(song: AlbumSong) {
        val uri = song.uri ?: return
        song.error = null
        song.file = null
        song.progress = 0f
        song.job?.cancel()
        song.job = viewModelScope.launch {
            try {
                song.file = graph.uploader.upload(uri, UploadKind.AUDIO) { song.progress = it }
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                song.error = e.message ?: "上传失败，请重试"
            }
        }
    }

    fun remove(song: AlbumSong) {
        song.job?.cancel()
        songs.remove(song)
    }

    fun uploadCover(context: android.content.Context, uri: Uri) {
        coverJob?.cancel()
        coverError = null
        coverRaw = null
        coverSquare = null
        coverProgress = 0f
        coverJob = viewModelScope.launch {
            try {
                val name = graph.uploader.displayName(uri)
                val prepared = withContext(Dispatchers.IO) { Images.prepareCover(context, uri, name) }
                coverPreview = prepared.preview
                try {
                    val rawName = if (name.contains('.')) name else "$name.jpg"
                    coverRaw = graph.uploader.upload(Uri.fromFile(prepared.raw), UploadKind.IMAGE, rawName) { coverProgress = it * 0.5f }
                    coverSquare = graph.uploader.upload(
                        Uri.fromFile(prepared.square), UploadKind.IMAGE, rawName.substringBeforeLast('.') + "_1v1.jpg",
                    ) { coverProgress = 0.5f + it * 0.5f }
                } finally {
                    prepared.raw.delete()
                    prepared.square.delete()
                }
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                coverError = e.message ?: "封面上传失败"
            }
        }
    }

    private fun validate(): String? = when {
        artist == null -> "请先选择要补充专辑的艺人"
        albumName.isBlank() -> "专辑名必填"
        albumArtists.isEmpty() -> "专辑艺人必填"
        company.isBlank() -> "发行公司必填"
        publishTime == null -> "发行时间必填"
        languages.isEmpty() -> "语种必填"
        albumType.isBlank() -> "类型必填"
        songs.isEmpty() -> "歌曲列表必填"
        tags.size > 3 -> "最多选择3个曲风"
        source.isBlank() -> "资料来源必填"
        songs.any { it.file == null } -> "歌曲音频尚未全部完成上传，请稍后再提交"
        songs.any { it.name.isBlank() || it.artists.isEmpty() || it.languages.isEmpty() } -> "有歌曲必填项暂未填写，请填写后重试"
        coverRaw == null && coverPreview != null && coverError == null -> "封面还在上传"
        !agreed -> "请同意《网易云音乐内容发布需知》"
        else -> null
    }

    private fun toJson(): JSONObject {
        val discs = JSONArray()
        songs.groupBy { it.disc }.toSortedMap().values.forEach { group ->
            group.forEachIndexed { index, song ->
                val audio = song.file!!.toJson()
                discs.put(
                    JSONObject()
                        .put("no", index + 1)
                        .put("songFId", song.songFId)
                        .put("songName", song.name.trim())
                        .put("transName", song.transName.trim())
                        .put("songSubTitle", song.subtitles.joinToString(";"))
                        .put("artistRepVos", JSONArray(song.artists.map { it.toJson() }))
                        .put("language", song.languages.joinToString(","))
                        .put("albumId", "")
                        .put("albumName", albumName.trim())
                        .put("disc", song.disc)
                        .put("songTags", JSONArray(song.tags.map { JSONObject().put("id", it.id).put("name", it.name) }))
                        .put("canEdit", true)
                        .put("changeType", 1)
                        .put("audio", audio)
                        .put("songMusicVo", audio),
                )
            }
        }
        val json = JSONObject()
            .put("albumName", albumName.trim())
            .put("subtitle", subtitles.joinToString(";"))
            .put("albumType", albumType)
            .put("transName", transName.trim())
            .put("artistIds", JSONArray(albumArtists.map { it.toJson() }))
            .put("company", company.trim())
            .put("publishTime", publishTime)
            .put("language", languages.joinToString(","))
            .put("songTags", JSONArray(tags.map { JSONObject().put("id", it.id).put("name", it.name) }))
            .put("production", production.trim())
        coverRaw?.let { json.put("albumRawNosKey", it.nosKey) }
        coverSquare?.let { json.put("album1v1NosKey", it.nosKey) }
        return json
            .put("albumSongDiscs", discs)
            .put("source", source.trim())
            .put("notes", notes.trim())
            .put("albumSongDiscVoList", discs)
    }

    fun submit(onToast: (String) -> Unit) {
        validate()?.let { onToast(it); return }
        val target = artist ?: return
        submitting = true
        viewModelScope.launch {
            try {
                graph.api.addAlbum(target.id, toJson())
                submitted = true
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                onToast(e.message ?: "提交失败")
            } finally {
                submitting = false
            }
        }
    }

    fun reset() {
        songs.forEach { it.job?.cancel() }
        coverJob?.cancel()
        songs.clear()
        albumName = ""; subtitles = emptyList(); albumType = "专辑"; transName = ""
        company = ""; publishTime = null; languages = emptyList(); tags = emptyList(); production = ""
        source = ""; notes = ""; agreed = false
        coverPreview = null; coverRaw = null; coverSquare = null; coverError = null; coverProgress = 0f
        albumArtists = artist?.let { listOf(WikiArtist(it.id, it.name, it.avatarUrl)) } ?: emptyList()
        submitted = false
    }
}

private sealed interface AlbumPicker {
    data object None : AlbumPicker
    data object Artist : AlbumPicker
    data object AlbumArtists : AlbumPicker
    data object Subtitles : AlbumPicker
    data object Date : AlbumPicker
    data object Languages : AlbumPicker
    data object Tags : AlbumPicker
    data class SongArtists(val song: AlbumSong) : AlbumPicker
    data class SongLanguages(val song: AlbumSong) : AlbumPicker
    data class SongTags(val song: AlbumSong) : AlbumPicker
    data class SongSubtitles(val song: AlbumSong) : AlbumPicker
}

@Composable
fun AlbumScreen(graph: AppGraph) {
    val vm: AlbumViewModel = viewModel { AlbumViewModel(graph) }
    val toast = LocalToast.current
    val context = LocalContext.current
    var picker by remember { mutableStateOf<AlbumPicker>(AlbumPicker.None) }
    val audioPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
        if (uris.isNotEmpty()) vm.addAudio(uris)
    }
    val coverPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        uri?.let { vm.uploadCover(context, it) }
    }

    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 24.dp + LocalBottomBarSpace.current),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item(key = "header") {
            Box(Modifier.statusBarsPadding()) { PageHeader("补充缺失专辑", "补充网易云缺失的专辑和歌曲，提交后由曲库审核") }
        }
        item(key = "artist") {
            SectionCard(
                "艺人",
                Modifier.enterAnimation(0),
                subtitle = "要给哪位艺人补充专辑。可以粘贴网页链接（…add-album?artistId=…）或艺人 ID，也可以搜索。",
            ) {
                AnimatedContent(
                    vm.artist,
                    transitionSpec = { (fadeIn(tween(260)) + scaleIn(tween(260), initialScale = 0.96f)) togetherWith fadeOut(tween(140)) },
                    label = "artist",
                ) { selected ->
                    if (selected != null) {
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(18.dp))
                                .background(MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f))
                                .padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            RemoteImage(selected.avatarUrl, null, Modifier.size(52.dp), CircleShape, fallback = selected.name)
                            Spacer(Modifier.width(12.dp))
                            Column(Modifier.weight(1f)) {
                                Text(selected.name, style = MaterialTheme.typography.titleMedium)
                                Text("ID ${selected.id}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            SoftButton("更换", { vm.artist = null }, icon = Icons.Rounded.SwapHoriz)
                        }
                    } else {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            AppTextField(
                                vm.artistInput, { vm.artistInput = it; vm.artistError = null }, "艺人链接或 ID",
                                error = vm.artistError,
                                onIme = { vm.confirmArtistInput() },
                            )
                            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                GradientButton("确定", { vm.confirmArtistInput() }, Modifier.weight(1f), loading = vm.artistLoading, icon = Icons.Rounded.Check)
                                SoftButton("搜索艺人", { picker = AlbumPicker.Artist }, icon = Icons.Rounded.Search, contentPadding = PaddingValues(horizontal = 16.dp, vertical = 15.dp))
                            }
                        }
                    }
                }
            }
        }
        item(key = "info") {
            SectionCard("专辑信息", Modifier.enterAnimation(1)) {
                AppTextField(vm.albumName, { vm.albumName = it }, "专辑名", required = true)
                SelectorField("副标题", vm.subtitles, { picker = AlbumPicker.Subtitles }, placeholder = "暂无",
                    onRemove = { i -> vm.subtitles = vm.subtitles.filterIndexed { j, _ -> j != i } })
                Text("类型 *", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                FlowRowCompat {
                    WikiApi.ALBUM_TYPES.forEach { type ->
                        FilterChip(selected = vm.albumType == type, onClick = { vm.albumType = type }, label = { Text(type) })
                    }
                }
                AppTextField(vm.transName, { vm.transName = it }, "翻译名")
                ArtistSelector("专辑艺人 *", vm.albumArtists, true, { picker = AlbumPicker.AlbumArtists }) { vm.albumArtists = it }
                AppTextField(vm.company, { vm.company = it }, "发行公司", required = true)
                SelectorField(
                    "发行时间", listOfNotNull(vm.publishTime?.let { SimpleDateFormat("yyyy-MM-dd", Locale.CHINA).format(Date(it)) }),
                    { picker = AlbumPicker.Date }, required = true, placeholder = "选择日期",
                )
                SelectorField("语种", vm.languages, { picker = AlbumPicker.Languages }, required = true,
                    onRemove = { i -> vm.languages = vm.languages.filterIndexed { j, _ -> j != i } })
                SelectorField("曲风（最多 3 个）", vm.tags.map { it.name }, { picker = AlbumPicker.Tags },
                    onRemove = { i -> vm.tags = vm.tags.filterIndexed { j, _ -> j != i } })
                AppTextField(vm.production, { vm.production = it }, "专辑介绍", singleLine = false, minLines = 3)
            }
        }
        item(key = "cover") {
            SectionCard("专辑图片", Modifier.enterAnimation(2), subtitle = "jpg / png，不小于 320×320，小于 20M") {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        Modifier
                            .size(112.dp)
                            .clip(RoundedCornerShape(20.dp))
                            .background(MaterialTheme.colorScheme.surfaceContainer)
                            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(20.dp))
                            .clickable { coverPicker.launch("image/*") },
                        contentAlignment = Alignment.Center,
                    ) {
                        AnimatedContent(vm.coverPreview, transitionSpec = { fadeIn(tween(300)) togetherWith fadeOut(tween(150)) }, label = "cover") { preview ->
                            if (preview != null) {
                                Image(preview.asImageBitmap(), "专辑封面", Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                            } else {
                                Icon(Icons.Rounded.AddPhotoAlternate, null, Modifier.size(36.dp), tint = MaterialTheme.colorScheme.primary)
                            }
                        }
                    }
                    Spacer(Modifier.width(16.dp))
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        SoftButton(if (vm.coverPreview == null) "添加" else "更换", { coverPicker.launch("image/*") }, icon = Icons.Rounded.AddPhotoAlternate)
                        when {
                            vm.coverError != null -> Notice(Icons.Rounded.WarningAmber, vm.coverError.orEmpty(), danger = true)
                            vm.coverSquare != null -> Notice(Icons.Rounded.CheckCircle, "已上传", success = true)
                            vm.coverPreview != null -> {
                                GradientProgress(vm.coverProgress)
                                Hint("上传中 ${(vm.coverProgress * 100).toInt()}%")
                            }
                        }
                    }
                }
            }
        }
        item(key = "songsHeader") {
            SectionCard(
                "歌曲列表 *",
                Modifier.enterAnimation(3),
                subtitle = "选择音频文件后立即开始上传（单个不超过 500M）。点歌曲可编辑名称、艺人、语种等。",
            ) {
                if (vm.songs.isEmpty()) EmptyState("还没有歌曲", icon = Icons.Rounded.LibraryAdd)
                SoftButton("添加音频", { audioPicker.launch("audio/*") }, Modifier.fillMaxWidth(), icon = Icons.Rounded.LibraryAdd)
            }
        }
        itemsIndexed(vm.songs, key = { _, song -> song.key }) { index, song ->
            AlbumSongCard(
                index, song,
                Modifier.animateItem(),
                onRetry = { vm.upload(song) },
                onRemove = { vm.remove(song) },
                onPick = { picker = it },
            )
        }
        item(key = "source") {
            SectionCard("资料来源", Modifier.enterAnimation(4)) {
                AppTextField(vm.source, { vm.source = it }, "资料来源", required = true, singleLine = false, minLines = 2, supporting = "资料来源的详细参考网址，多个用换行隔开")
                AppTextField(vm.notes, { vm.notes = it }, "补充备注", singleLine = false, minLines = 2, supporting = "只会被审核人员看到")
                Row(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).clickable { vm.agreed = !vm.agreed }.padding(vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Checkbox(vm.agreed, { vm.agreed = it })
                    Text(
                        "我已阅读并同意《网易云音乐内容发布需知》，并确认提交的音频与资料不侵犯他人权利",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                GradientButton(if (vm.submitting) "提交中…" else "提交审核", { vm.submit(toast) }, Modifier.fillMaxWidth(), loading = vm.submitting, icon = Icons.AutoMirrored.Rounded.Send)
            }
        }
    }

    when (val p = picker) {
        AlbumPicker.None -> Unit
        AlbumPicker.Artist -> ArtistPickerSheet(
            search = vm::searchArtists,
            onPick = { a -> picker = AlbumPicker.None; a.id?.let(vm::loadArtist) },
            onDismiss = { picker = AlbumPicker.None },
            allowNew = false,
            title = "搜索艺人",
        )
        AlbumPicker.AlbumArtists -> ArtistPickerSheet(vm::searchArtists, { vm.albumArtists = vm.albumArtists + it; picker = AlbumPicker.None }, { picker = AlbumPicker.None })
        AlbumPicker.Subtitles -> LinesEditorSheet("副标题", "每行一个，例：游戏《xx》原声集", vm.subtitles, { vm.subtitles = it; picker = AlbumPicker.None }) { picker = AlbumPicker.None }
        AlbumPicker.Date -> DatePickerSheet(vm.publishTime, { vm.publishTime = it }) { picker = AlbumPicker.None }
        AlbumPicker.Languages -> LanguagePickerSheet(WikiApi.LANGUAGES, WikiApi.EXCLUSIVE_LANGUAGES, vm.languages, { vm.languages = it; picker = AlbumPicker.None }) { picker = AlbumPicker.None }
        AlbumPicker.Tags -> TagPickerSheet(vm::searchTags, vm.tags, { vm.tags = it; picker = AlbumPicker.None }) { picker = AlbumPicker.None }
        is AlbumPicker.SongArtists -> ArtistPickerSheet(vm::searchArtists, { p.song.artists = p.song.artists + it; picker = AlbumPicker.None }, { picker = AlbumPicker.None })
        is AlbumPicker.SongLanguages -> LanguagePickerSheet(WikiApi.LANGUAGES, WikiApi.EXCLUSIVE_LANGUAGES, p.song.languages, { p.song.languages = it; picker = AlbumPicker.None }) { picker = AlbumPicker.None }
        is AlbumPicker.SongTags -> TagPickerSheet(vm::searchTags, p.song.tags, { p.song.tags = it; picker = AlbumPicker.None }) { picker = AlbumPicker.None }
        is AlbumPicker.SongSubtitles -> LinesEditorSheet("副标题", "每行一个", p.song.subtitles, { p.song.subtitles = it; picker = AlbumPicker.None }) { picker = AlbumPicker.None }
    }

    if (vm.submitted) {
        AlertDialog(
            onDismissRequest = { vm.reset() },
            icon = { Icon(Icons.Rounded.CheckCircle, null, tint = LocalBrand.current.success) },
            title = { Text("已提交") },
            text = { Text("专辑已提交给网易云曲库审核，可以在「我的 → 我的贡献 → 补充专辑」查看进度。") },
            confirmButton = { TextButton(onClick = { vm.reset() }) { Text("好的") } },
        )
    }
}

@Composable
private fun AlbumSongCard(
    index: Int,
    song: AlbumSong,
    modifier: Modifier,
    onRetry: () -> Unit,
    onRemove: () -> Unit,
    onPick: (AlbumPicker) -> Unit,
) {
    val rotation by animateFloatAsState(if (song.expanded) 180f else 0f, spring(stiffness = Spring.StiffnessMediumLow), label = "chevron")
    Column(
        modifier
            .fillMaxWidth()
            .enterAnimation(index, song.key)
            .clip(MaterialTheme.shapes.large)
            .background(MaterialTheme.colorScheme.surfaceContainerLow)
            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, MaterialTheme.shapes.large)
            .animateContentSize(spring(stiffness = Spring.StiffnessMediumLow)),
    ) {
        Row(
            Modifier.fillMaxWidth().clickable { song.expanded = !song.expanded }.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                Modifier.size(36.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primaryContainer),
                contentAlignment = Alignment.Center,
            ) { Text("${index + 1}", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onPrimaryContainer) }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(song.name.ifBlank { "（未命名）" }, style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                val meta = listOf(
                    song.artists.joinToString(" / ") { it.name }.ifBlank { "未填艺人" },
                    song.languages.joinToString(",").ifBlank { "未填语种" },
                    "Disc ${song.disc}",
                ).joinToString(" · ")
                Text(meta, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            Icon(Icons.Rounded.ExpandMore, "编辑", Modifier.graphicsLayer { rotationZ = rotation })
        }
        Column(Modifier.padding(horizontal = 14.dp).padding(bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            when {
                song.error != null -> Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.weight(1f)) { Notice(Icons.Rounded.WarningAmber, song.error.orEmpty(), danger = true) }
                    TextButton(onClick = onRetry) { Text("重试") }
                }
                song.file != null -> Notice(Icons.Rounded.CheckCircle, "上传成功 · ${song.fileName}", success = true)
                else -> {
                    GradientProgress(song.progress)
                    Hint("${song.fileName} · 上传中 ${(song.progress * 100).toInt()}%")
                }
            }
        }
        Reveal(song.expanded) {
            Column(Modifier.padding(horizontal = 14.dp).padding(bottom = 14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                AppTextField(song.name, { song.name = it }, "歌曲名", required = true)
                AppTextField(song.transName, { song.transName = it }, "翻译名")
                Text("盘符 Disc", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                FlowRowCompat {
                    (1..6).forEach { disc ->
                        FilterChip(selected = song.disc == disc, onClick = { song.disc = disc }, label = { Text("Disc $disc") })
                    }
                }
                SelectorField("副标题", song.subtitles, { onPick(AlbumPicker.SongSubtitles(song)) }, placeholder = "暂无",
                    onRemove = { i -> song.subtitles = song.subtitles.filterIndexed { j, _ -> j != i } })
                ArtistSelector("歌曲艺人 *", song.artists, true, { onPick(AlbumPicker.SongArtists(song)) }) { song.artists = it }
                SelectorField("语种", song.languages, { onPick(AlbumPicker.SongLanguages(song)) }, required = true,
                    onRemove = { i -> song.languages = song.languages.filterIndexed { j, _ -> j != i } })
                SelectorField("曲风", song.tags.map { it.name }, { onPick(AlbumPicker.SongTags(song)) },
                    onRemove = { i -> song.tags = song.tags.filterIndexed { j, _ -> j != i } })
                Row(horizontalArrangement = Arrangement.End, modifier = Modifier.fillMaxWidth()) {
                    TextButton(onClick = onRemove) {
                        Icon(Icons.Rounded.DeleteOutline, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("移除")
                    }
                    TextButton(onClick = { song.expanded = false }) { Text("完成") }
                }
            }
        }
    }
}

