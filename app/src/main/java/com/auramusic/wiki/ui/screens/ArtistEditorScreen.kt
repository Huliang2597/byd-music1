package com.auramusic.wiki.ui.screens

import android.content.ClipboardManager
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.RectF
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AccountCircle
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.ContentPaste
import androidx.compose.material.icons.rounded.Crop
import androidx.compose.material.icons.automirrored.rounded.OpenInNew
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.auramusic.wiki.AppGraph
import com.auramusic.wiki.data.ArtistWiki
import com.auramusic.wiki.data.Images
import com.auramusic.wiki.data.Links
import com.auramusic.wiki.data.PublicWiki
import com.auramusic.wiki.ui.LocalNav
import com.auramusic.wiki.ui.components.AppTextField
import com.auramusic.wiki.ui.components.ChoiceSheet
import com.auramusic.wiki.ui.components.GradientButton
import com.auramusic.wiki.ui.components.Hint
import com.auramusic.wiki.ui.components.LocalToast
import com.auramusic.wiki.ui.components.PageHeader
import com.auramusic.wiki.ui.components.RemoteImage
import com.auramusic.wiki.ui.components.Reveal
import com.auramusic.wiki.ui.components.SectionCard
import com.auramusic.wiki.ui.components.SelectorField
import com.auramusic.wiki.ui.components.SoftButton
import com.auramusic.wiki.ui.components.enterAnimation
import com.auramusic.wiki.ui.theme.LocalBrand
import java.io.IOException
import kotlin.math.roundToInt
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

class PreparedImages(val raw: ByteArray, val head: ByteArray, val avatar: ByteArray)

private val TEXT_FIELDS = listOf(
    Triple("artistName", "艺人名", false),
    Triple("alias", "别名 · 多个名称用换行或分号分隔", true),
    Triple("transName", "翻译名", false),
)
private val LONG_FIELDS = listOf(
    Triple("desc", "艺人简介 · 最多 2048 字", 2048),
    Triple("production", "详细介绍", 100000),
)

class ArtistEditorViewModel(private val graph: AppGraph) : ViewModel() {
    var input by mutableStateOf("")
    var inputError by mutableStateOf<String?>(null)
    var status by mutableStateOf("登录后可读取和修改艺人资料")
    var busy by mutableStateOf(false)
    var matches by mutableStateOf<List<JSONObject>>(emptyList())
    var account by mutableStateOf("")
    var artistId by mutableStateOf<String?>(null)
    var original by mutableStateOf<JSONObject?>(null)
    var permissions by mutableStateOf(JSONObject())
    private var loadedCredential: String? = null
    var submitted by mutableStateOf(false)
    val texts = mutableStateMapOf<String, String>()
    val choices = mutableStateMapOf<String, Int>()
    val choiceOptions = mutableStateMapOf<String, List<Pair<Int, String>>>()
    var source by mutableStateOf("")
    var sourceError by mutableStateOf<String?>(null)
    var notes by mutableStateOf("")
    var prepared by mutableStateOf<PreparedImages?>(null)
    var headPreview by mutableStateOf<ImageBitmap?>(null)
    var avatarPreview by mutableStateOf<ImageBitmap?>(null)
    var cropSource by mutableStateOf<Bitmap?>(null)
    var review by mutableStateOf<Pair<String, JSONObject>?>(null)
    var success by mutableStateOf(false)
    private var job: Job? = null
    private var started = false

    fun start(query: String?) {
        if (started && query == null) return
        started = true
        refreshAccount()
        input = query ?: graph.drafts.getString("last_artist", "").orEmpty()
        if (query != null) query()
    }

    fun editable(key: String) = permissions.optBoolean(key, false)

    fun refreshAccount() {
        val name = graph.session.account.value?.nickname?.ifBlank { null } ?: "未登录"
        account = name + if (graph.session.credential().isEmpty()) " · 请先登录" else " · 网易云账号"
    }

    private fun client(credential: String) = ArtistWiki(credential)

    private fun message(e: Throwable) = e.message ?: "操作失败，请检查网络后重试"

    private fun launch(statusText: String, block: suspend () -> Unit) {
        job?.cancel()
        busy = true
        status = statusText
        job = viewModelScope.launch {
            try {
                block()
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                busy = false
                status = message(e)
            }
        }
    }

    fun query() {
        if (busy) return
        val text = input.trim()
        if (text.isEmpty()) {
            inputError = "请输入艺人名、ID 或艺人链接"
            return
        }
        saveDraft()
        inputError = null
        val id = ArtistWiki.normalizeId(text)
        if (id == null && text.matches(Regex("(?is).*https?://.*"))) {
            inputError = "请输入网易云艺人链接；歌曲链接和短链接不适用"
            return
        }
        if (id != null) {
            load(id)
            return
        }
        val credential = graph.session.credential()
        if (credential.isEmpty()) {
            status = "请先登录，再查询艺人"
            return
        }
        launch("正在搜索艺人…") {
            val list = client(credential).search(text)
            matches = (0 until list.length()).mapNotNull { list.optJSONObject(it) }
                .filter { it.optString("artistId").matches(Regex("[1-9][0-9]{0,19}")) }
            busy = false
            status = if (list.length() == 0) "没有找到艺人，请尝试 ID 或其他名称" else "请选择要修改的艺人"
        }
    }

    fun pick(id: String) {
        if (busy) return
        input = id
        saveDraft()
        load(id)
    }

    fun load(id: String) {
        val credential = graph.session.credential()
        if (credential.isEmpty()) {
            status = "请先登录，再读取艺人资料"
            return
        }
        launch("正在读取艺人资料及修改权限…") {
            val api = client(credential)
            val data = api.get(id)
            var problem = ""
            val perms = try {
                api.permissions(id)
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                problem = message(e)
                JSONObject()
            }
            if (graph.session.credential() != credential) {
                busy = false
                status = "登录账号已变化，请重新读取资料"
                return@launch
            }
            render(id, data, perms, credential)
            busy = false
            status = if (problem.isEmpty()) "已读取，灰色字段当前不可修改" else "已读取资料；$problem"
        }
    }

    private fun render(id: String, data: JSONObject, perms: JSONObject, credential: String) {
        prepared = null
        headPreview = null
        avatarPreview = null
        artistId = id
        original = data
        permissions = perms
        loadedCredential = credential
        submitted = false
        matches = emptyList()
        graph.drafts.edit().putString("last_artist", id).apply()
        texts.clear()
        (TEXT_FIELDS.map { it.first } + LONG_FIELDS.map { it.first }).forEach { key ->
            var value = ArtistWiki.text(data, key)
            if (key == "alias") value = value.replace(';', '\n')
            texts[key] = value
        }
        choices.clear()
        choiceOptions.clear()
        listOf(
            Triple("area", ArtistWiki.AREAS, ArtistWiki.AREA_NAMES),
            Triple("type", ArtistWiki.TYPES, ArtistWiki.TYPE_NAMES),
        ).forEach { (key, values, names) ->
            val current = data.optInt(key, 0)
            val options = values.indices.map { values[it] to names[it] }.toMutableList()
            if (options.none { it.first == current }) options.add(current to "保留原值 $current")
            choiceOptions[key] = options
            choices[key] = current
        }
        source = ""
        notes = ""
        restoreDraft()
    }

    private fun edited(): JSONObject {
        val json = JSONObject()
        texts.forEach { (key, value) -> json.put(key, value) }
        choices.forEach { (key, value) -> json.put(key, value) }
        return json
    }

    fun saveDraft() {
        val base = original ?: return
        val id = artistId ?: return
        if (submitted) return
        runCatching {
            graph.drafts.edit().putString(
                "artist_$id",
                JSONObject().put("values", edited()).put("baseline", base).put("source", source).put("notes", notes).toString(),
            ).apply()
        }
    }

    private fun restoreDraft() {
        val base = original ?: return
        runCatching {
            val raw = graph.drafts.getString("artist_$artistId", null) ?: return
            val draft = JSONObject(raw)
            val values = draft.getJSONObject("values")
            val baseline = draft.optJSONObject("baseline")
            for (key in texts.keys.toList()) {
                if (values.has(key) && editable(key) && ArtistWiki.text(base, key) == ArtistWiki.text(baseline, key)) {
                    var value = ArtistWiki.text(values, key)
                    if (key == "alias") value = value.replace(';', '\n')
                    texts[key] = value
                }
            }
            for (key in choices.keys.toList()) {
                if (editable(key) && ArtistWiki.text(base, key) == ArtistWiki.text(baseline, key)) {
                    val value = values.optInt(key, base.optInt(key))
                    if (choiceOptions[key]?.any { it.first == value } == true) choices[key] = value
                }
            }
            source = draft.optString("source")
            notes = draft.optString("notes")
        }
    }

    private fun shorten(text: String) = when {
        text.isEmpty() -> "空"
        text.length > 180 -> text.substring(0, 180) + "…"
        else -> text
    }

    private fun display(json: JSONObject, key: String): String {
        if (key == "area" || key == "type") {
            val values = if (key == "area") ArtistWiki.AREAS else ArtistWiki.TYPES
            val names = if (key == "area") ArtistWiki.AREA_NAMES else ArtistWiki.TYPE_NAMES
            val index = values.indexOf(json.optInt(key, 0))
            if (index >= 0) return names[index]
        }
        return ArtistWiki.text(json, key)
    }

    fun review() {
        val base = original ?: return
        if (busy || submitted) return
        try {
            if (graph.session.credential() != loadedCredential) throw IOException("登录账号已变化，请重新读取资料")
            val values = edited()
            val change = ArtistWiki.changes(
                artistId.orEmpty(), base, values, permissions,
                if (prepared != null) ArtistWiki.pendingImages() else null, source, notes,
            )
            val text = buildString {
                append(base.optString("artistName")).append(" · ID ").append(artistId).append("\n\n")
                for (key in ArtistWiki.KEYS) {
                    if (key == "img") {
                        if (prepared != null) append("艺人图片：主页图与头像已裁剪\n\n")
                    } else if (change.has(key)) {
                        append(ArtistWiki.label(key)).append("\n原：").append(shorten(display(base, key)))
                            .append("\n改：").append(shorten(display(change, key))).append("\n\n")
                    }
                }
                append("资料来源：").append(shorten(source)).append("\n\n提交后等待网易云审核。")
            }
            review = text to values
        } catch (e: Exception) {
            status = message(e)
            if (source.isBlank()) sourceError = "资料来源必填"
        }
    }

    fun send(values: JSONObject) {
        review = null
        if (busy || submitted) return
        val credential = graph.session.credential()
        if (credential != loadedCredential) {
            status = "登录账号已变化，请重新读取资料"
            return
        }
        val id = artistId ?: return
        val base = original ?: return
        val images = prepared
        val sourceText = source
        val notesText = notes
        launch("正在核对修改权限…") {
            val api = client(credential)
            var attempted = false
            try {
                val change = ArtistWiki.changes(id, base, values, api.permissions(id), if (images == null) null else ArtistWiki.pendingImages(), sourceText, notesText)
                ArtistWiki.checkConflicts(base, api.get(id), change)
                if (graph.session.credential() != credential) throw IOException("登录账号已变化，请重新读取资料")
                if (images != null) {
                    status = "正在上传艺人原图、主页图与头像…"
                    val raw = api.uploadImage(images.raw)
                    change.put("artistRawCover", raw).put("artistHeadRawCover", raw)
                        .put("artistMainPageCover", api.uploadImage(images.head))
                        .put("artistHeadCover", api.uploadImage(images.avatar))
                }
                if (graph.session.credential() != credential) throw IOException("登录账号已变化，请重新读取资料")
                status = "正在提交修改，请稍候…"
                attempted = true
                api.submit(change)
                submitted = true
                busy = false
                status = "已提交，等待网易云审核；审核通过后资料才会更新"
                graph.drafts.edit().remove("artist_$id").apply()
                prepared = null
                success = true
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                busy = false
                status = if (attempted && e !is ArtistWiki.ApiException) {
                    message(e) + "。尚未确认提交结果，请先核对网易云贡献记录再重试"
                } else {
                    message(e)
                }
            }
        }
    }

    fun readImage(context: Context, uri: Uri) {
        if (busy || original == null || !editable("img")) return
        launch("正在读取图片…") {
            val bitmap = withContext(Dispatchers.IO) {
                val bytes = (context.contentResolver.openInputStream(uri) ?: throw IOException("无法读取图片")).use { input ->
                    val out = java.io.ByteArrayOutputStream()
                    val buffer = ByteArray(8192)
                    while (true) {
                        val read = input.read(buffer)
                        if (read < 0) break
                        if (out.size() + read > 20 * 1024 * 1024) throw IOException("图片过大或为空")
                        out.write(buffer, 0, read)
                    }
                    out.toByteArray()
                }
                Images.decodeArtist(bytes)
            }
            busy = false
            status = "拖动图片调整头像和主页图"
            cropSource = bitmap
        }
    }

    fun acceptCrop(images: PreparedImages) {
        prepared = images
        headPreview = BitmapFactory.decodeByteArray(images.head, 0, images.head.size)?.asImageBitmap()
        avatarPreview = BitmapFactory.decodeByteArray(images.avatar, 0, images.avatar.size)?.asImageBitmap()
        status = "图片已在本机裁剪，提交时上传"
        cropSource = null
    }

    override fun onCleared() {
        saveDraft()
        super.onCleared()
    }
}

@Composable
fun ArtistEditorScreen(graph: AppGraph, query: String?, onClose: () -> Unit) {
    val vm: ArtistEditorViewModel = viewModel { ArtistEditorViewModel(graph) }
    val nav = LocalNav.current
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val toast = LocalToast.current
    var choiceKey by remember { mutableStateOf<String?>(null) }
    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri?.let { vm.readImage(context, it) }
    }
    LaunchedEffect(query) { vm.start(query) }
    LifecycleEventEffect(Lifecycle.Event.ON_PAUSE) { vm.saveDraft() }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { vm.refreshAccount() }
    val close = {
        vm.saveDraft()
        onClose()
    }

    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        LazyColumn(
            Modifier.fillMaxSize().imePadding().navigationBarsPadding(),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item(key = "header") {
                Box(Modifier.statusBarsPadding()) {
                    PageHeader("艺人资料修改", "搜索艺人，或粘贴艺人 ID、网易云艺人链接。修改会提交至网易云审核。", onBack = close)
                }
            }
            item(key = "search") {
                SectionCard(null, Modifier.enterAnimation(0)) {
                    AppTextField(
                        vm.input, { vm.input = it; vm.inputError = null }, "艺人名、ID 或艺人链接",
                        leading = Icons.Rounded.Search,
                        error = vm.inputError,
                        imeAction = ImeAction.Search,
                        onIme = { focus.clearFocus(); vm.query() },
                        trailing = {
                            IconButton(onClick = {
                                val clip = (context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).primaryClip
                                if (clip != null && clip.itemCount > 0) vm.input = clip.getItemAt(0).coerceToText(context).toString()
                            }) { Icon(Icons.Rounded.ContentPaste, "粘贴") }
                        },
                    )
                    GradientButton("查询艺人", { focus.clearFocus(); vm.query() }, Modifier.fillMaxWidth(), enabled = !vm.busy, icon = Icons.Rounded.Search)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Rounded.AccountCircle, null, Modifier.size(18.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.width(6.dp))
                        Text(vm.account, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f))
                        SoftButton(
                            "登录/换号",
                            {
                                nav.officialLogin = { result ->
                                    runCatching { graph.session.accept(result) }.onFailure { toast(it.message ?: "登录失败") }
                                    vm.refreshAccount()
                                    if (vm.input.isNotBlank()) vm.query()
                                }
                            },
                            enabled = !vm.busy,
                        )
                    }
                }
            }
            item(key = "status") {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Reveal(vm.busy) { LinearProgressIndicator(Modifier.fillMaxWidth().clip(CircleShape)) }
                    AnimatedContent(vm.status, transitionSpec = { fadeIn(tween(200)) togetherWith fadeOut(tween(120)) }, label = "artistStatus") {
                        Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(horizontal = 6.dp))
                    }
                }
            }
            itemsIndexed(vm.matches, key = { i, m -> "match-" + m.optString("artistId") + "-$i" }) { index, match ->
                val id = match.optString("artistId")
                Row(
                    Modifier
                        .animateItem()
                        .enterAnimation(index, id)
                        .fillMaxWidth()
                        .clip(MaterialTheme.shapes.large)
                        .background(MaterialTheme.colorScheme.surfaceContainerLow)
                        .clickable { vm.pick(id) }
                        .padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    RemoteImage(
                        PublicWiki.thumbnail(match.optString("artistAvatarPicUrl"), 128), null,
                        Modifier.size(46.dp), CircleShape, fallback = match.optString("artistName"),
                    )
                    Spacer(Modifier.width(12.dp))
                    Column {
                        Text(match.optString("artistName", "未知艺人"), style = MaterialTheme.typography.titleSmall)
                        Text("ID $id", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            val base = vm.original
            if (base != null) {
                item(key = "form-head") {
                    Row(Modifier.enterAnimation(0, vm.artistId), verticalAlignment = Alignment.CenterVertically) {
                        Text("${base.optString("artistName")} · ID ${vm.artistId}", style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
                        IconButton(onClick = { Links.open(context, "https://music.163.com/artist?id=${vm.artistId}") }) {
                            Icon(Icons.AutoMirrored.Rounded.OpenInNew, "在网易云查看艺人")
                        }
                    }
                }
                item(key = "form-basic") {
                    SectionCard("基本资料", Modifier.enterAnimation(1, vm.artistId)) {
                        TEXT_FIELDS.forEach { (key, label, multi) ->
                            val editable = vm.editable(key) && !vm.busy && !vm.submitted
                            AppTextField(
                                vm.texts[key].orEmpty(), { vm.texts[key] = it },
                                label + if (vm.editable(key)) "" else " · 当前不可修改",
                                placeholder = "暂无资料", singleLine = !multi, minLines = if (multi) 2 else 1, enabled = editable,
                            )
                        }
                        listOf("area" to "地区", "type" to "类型").forEach { (key, label) ->
                            val current = vm.choices[key]
                            SelectorField(
                                label + if (vm.editable(key)) "" else " · 当前不可修改",
                                listOfNotNull(vm.choiceOptions[key]?.firstOrNull { it.first == current }?.second),
                                { choiceKey = key },
                                enabled = vm.editable(key) && !vm.busy && !vm.submitted,
                            )
                        }
                    }
                }
                item(key = "form-images") {
                    SectionCard(
                        "艺人图片" + if (vm.editable("img")) "" else " · 当前不可修改",
                        Modifier.enterAnimation(2, vm.artistId),
                        subtitle = "主页图 640 × 520，头像 400 × 400",
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Preview(vm.headPreview, PublicWiki.thumbnail(base.optString("headPicUrl"), 300), "艺人主页图片", Modifier.weight(1f).height(110.dp), RoundedCornerShape(18.dp))
                            Spacer(Modifier.width(12.dp))
                            Preview(vm.avatarPreview, PublicWiki.thumbnail(base.optString("avatarPicUrl"), 300), "艺人头像", Modifier.size(92.dp), CircleShape)
                        }
                        SoftButton(
                            "选择并裁剪图片",
                            { imagePicker.launch(arrayOf("image/jpeg", "image/png")) },
                            Modifier.fillMaxWidth(),
                            enabled = vm.editable("img") && !vm.busy && !vm.submitted,
                            icon = Icons.Rounded.Crop,
                        )
                    }
                }
                item(key = "form-long") {
                    SectionCard("介绍", Modifier.enterAnimation(3, vm.artistId)) {
                        LONG_FIELDS.forEach { (key, label, _) ->
                            AppTextField(
                                vm.texts[key].orEmpty(),
                                { value -> vm.texts[key] = value },
                                label + if (vm.editable(key)) "" else " · 当前不可修改",
                                placeholder = "暂无资料", singleLine = false, minLines = 3,
                                enabled = vm.editable(key) && !vm.busy && !vm.submitted,
                                supporting = if (key == "desc") "${vm.texts[key].orEmpty().length} / 2048" else null,
                            )
                        }
                    }
                }
                item(key = "form-source") {
                    SectionCard("资料来源", Modifier.enterAnimation(4, vm.artistId)) {
                        AppTextField(
                            vm.source, { vm.source = it.take(8192); vm.sourceError = null }, "资料来源", required = true,
                            placeholder = "艺人官网、官方介绍或其他可核实来源", singleLine = false, minLines = 2,
                            error = vm.sourceError, enabled = !vm.busy && !vm.submitted,
                        )
                        AppTextField(
                            vm.notes, { vm.notes = it.take(8192) }, "补充备注",
                            placeholder = "说明本次修改的原因，可不填", singleLine = false, minLines = 2,
                            enabled = !vm.busy && !vm.submitted,
                        )
                        GradientButton(
                            if (vm.submitted) "已提交审核" else "预览并提交修改",
                            { vm.review() },
                            Modifier.fillMaxWidth(),
                            enabled = !vm.submitted,
                            loading = vm.busy,
                            icon = Icons.AutoMirrored.Rounded.Send,
                        )
                        SoftButton("重新读取资料", { vm.saveDraft(); vm.artistId?.let(vm::load) }, Modifier.fillMaxWidth(), enabled = !vm.busy, icon = Icons.Rounded.Refresh)
                        Hint("文字草稿会保存在本机。未提交的图片需要重新选择。")
                    }
                }
            }
        }
    }

    choiceKey?.let { key ->
        ChoiceSheet(
            if (key == "area") "地区" else "类型",
            vm.choiceOptions[key].orEmpty(),
            vm.choices[key],
            { vm.choices[key] = it; choiceKey = null },
            { choiceKey = null },
        )
    }

    vm.review?.let { (text, values) ->
        AlertDialog(
            onDismissRequest = { vm.review = null },
            title = { Text("确认艺人资料修改") },
            text = {
                Box(Modifier.height(360.dp).verticalScroll(rememberScrollState())) {
                    androidx.compose.foundation.text.selection.SelectionContainer {
                        Text(text, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            },
            confirmButton = { TextButton(onClick = { vm.send(values) }) { Text("提交审核") } },
            dismissButton = { TextButton(onClick = { vm.review = null }) { Text("继续编辑") } },
        )
    }

    if (vm.success) {
        AlertDialog(
            onDismissRequest = { vm.success = false },
            icon = { Icon(Icons.Rounded.CheckCircle, null, tint = LocalBrand.current.success) },
            title = { Text("已提交审核") },
            text = { Text("艺人资料修改已提交。可在网易云贡献记录中查看审核进度。") },
            confirmButton = { TextButton(onClick = { vm.success = false }) { Text("完成") } },
            dismissButton = {
                TextButton(onClick = {
                    vm.success = false
                    Links.browse(context, "https://music.163.com/#/wiki/contribution")
                }) { Text("查看贡献记录") }
            },
        )
    }

    vm.cropSource?.let { source ->
        CropDialog(
            source,
            onDone = { vm.acceptCrop(it) },
            onDismiss = { vm.cropSource = null },
        )
    }
}

@Composable
private fun Preview(local: ImageBitmap?, remote: String?, description: String, modifier: Modifier, shape: androidx.compose.ui.graphics.Shape) {
    AnimatedContent(local, transitionSpec = { fadeIn(tween(320)) togetherWith fadeOut(tween(160)) }, label = "preview", modifier = modifier) { bitmap ->
        if (bitmap != null) {
            Image(bitmap, description, Modifier.fillMaxSize().clip(shape), contentScale = ContentScale.Crop)
        } else {
            RemoteImage(remote, description, Modifier.fillMaxSize(), shape)
        }
    }
}

/** 拖动、双指缩放调整构图的裁剪区域。 */
private class CropState(val source: Bitmap, val aspect: Float) {
    var cx by mutableFloatStateOf(0.5f)
    var cy by mutableFloatStateOf(0.5f)
    var zoom by mutableFloatStateOf(1f)
    var size by mutableStateOf(IntSize.Zero)

    data class Geometry(val crop: RectF, val scale: Float)

    fun geometry(): Geometry? {
        if (size.width == 0 || size.height == 0) return null
        var w = size.width - 16f
        var h = size.height - 16f
        if (w / h > aspect) w = aspect * h else h = w / aspect
        val crop = RectF((size.width - w) / 2f, (size.height - h) / 2f, (size.width + w) / 2f, (size.height + h) / 2f)
        val scale = maxOf(w / source.width, h / source.height) * zoom
        val mx = w / (scale * 2f * source.width)
        val my = h / (scale * 2f * source.height)
        cx = cx.coerceIn(mx, 1f - mx)
        cy = cy.coerceIn(my, 1f - my)
        return Geometry(crop, scale)
    }

    fun pan(dx: Float, dy: Float, factor: Float) {
        zoom = (zoom * factor).coerceIn(1f, 4f)
        val g = geometry() ?: return
        cx -= dx / (source.width * g.scale)
        cy -= dy / (source.height * g.scale)
        geometry()
    }

    fun valid(width: Int, height: Int): Boolean {
        val g = geometry() ?: return false
        return g.crop.width() / g.scale + 0.5f >= width && g.crop.height() / g.scale + 0.5f >= height
    }

    fun export(width: Int, height: Int): ByteArray {
        val g = geometry() ?: throw IOException("图片处理失败")
        val halfW = g.crop.width() / (g.scale * 2f)
        val halfH = g.crop.height() / (g.scale * 2f)
        val region = RectF(cx * source.width - halfW, cy * source.height - halfH, cx * source.width + halfW, cy * source.height + halfH)
        return Images.export(source, region, width, height)
    }
}

@Composable
private fun CropBox(state: CropState, circle: Boolean, modifier: Modifier) {
    val image = remember(state.source) { state.source.asImageBitmap() }
    Canvas(
        modifier
            .clip(RoundedCornerShape(18.dp))
            .background(Color.Black)
            .onSizeChanged { state.size = it }
            .pointerInput(state) {
                detectTransformGestures { _, pan, zoom, _ -> state.pan(pan.x, pan.y, zoom) }
            },
    ) {
        val g = state.geometry() ?: return@Canvas
        val left = g.crop.centerX() - state.cx * state.source.width * g.scale
        val top = g.crop.centerY() - state.cy * state.source.height * g.scale
        drawImage(
            image,
            dstOffset = IntOffset(left.roundToInt(), top.roundToInt()),
            dstSize = IntSize((state.source.width * g.scale).roundToInt(), (state.source.height * g.scale).roundToInt()),
        )
        val shade = Color.Black.copy(alpha = 0.6f)
        drawRect(shade, Offset.Zero, Size(size.width, g.crop.top))
        drawRect(shade, Offset(0f, g.crop.bottom), Size(size.width, size.height - g.crop.bottom))
        drawRect(shade, Offset(0f, g.crop.top), Size(g.crop.left, g.crop.height()))
        drawRect(shade, Offset(g.crop.right, g.crop.top), Size(size.width - g.crop.right, g.crop.height()))
        val topLeft = Offset(g.crop.left, g.crop.top)
        val cropSize = Size(g.crop.width(), g.crop.height())
        drawRoundRect(Color.White, topLeft, cropSize, CornerRadius(6f), style = Stroke(2.dp.toPx()))
        if (circle) drawOval(Color.White.copy(alpha = 0.7f), topLeft, cropSize, style = Stroke(1.dp.toPx()))
        // 三分线
        for (i in 1..2) {
            val x = g.crop.left + g.crop.width() * i / 3f
            val y = g.crop.top + g.crop.height() * i / 3f
            drawLine(Color.White.copy(alpha = 0.35f), Offset(x, g.crop.top), Offset(x, g.crop.bottom), 1f)
            drawLine(Color.White.copy(alpha = 0.35f), Offset(g.crop.left, y), Offset(g.crop.right, y), 1f)
        }
    }
}

@Composable
private fun CropDialog(source: Bitmap, onDone: (PreparedImages) -> Unit, onDismiss: () -> Unit) {
    val toast = LocalToast.current
    val head = remember(source) { CropState(source, 640f / 520f) }
    val avatar = remember(source) { CropState(source, 1f) }
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.surface) {
            Column(
                Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text("调整艺人图片", style = MaterialTheme.typography.titleLarge)
                Hint("分别拖动或双指缩放两张图片，调整构图。点击完成后返回资料页，提交时才上传。")
                Text("艺人主页图片 · 640 × 520", style = MaterialTheme.typography.labelLarge)
                CropBox(head, false, Modifier.fillMaxWidth().weight(1f))
                Text("艺人头像 · 400 × 400", style = MaterialTheme.typography.labelLarge)
                CropBox(avatar, true, Modifier.fillMaxWidth().weight(1f))
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    SoftButton("取消", onDismiss, Modifier.weight(1f))
                    GradientButton(
                        "完成",
                        {
                            try {
                                if (!head.valid(640, 520) || !avatar.valid(400, 400)) throw IOException("缩放过大，裁剪区域像素不足，请缩小图片后重试")
                                val images = PreparedImages(Images.jpeg(source), head.export(640, 520), avatar.export(400, 400))
                                onDone(images)
                            } catch (e: Exception) {
                                toast(e.message ?: "图片处理失败")
                            }
                        },
                        Modifier.weight(1f),
                    )
                }
            }
        }
    }
}

