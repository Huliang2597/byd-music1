package com.auramusic.wiki.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.ExperimentalFoundationApi
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
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.ContentCopy
import androidx.compose.material.icons.rounded.ContentPaste
import androidx.compose.material.icons.rounded.History
import androidx.compose.material.icons.automirrored.rounded.OpenInNew
import androidx.compose.material.icons.rounded.Person
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.TravelExplore
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.auramusic.wiki.AppGraph
import com.auramusic.wiki.data.Links
import com.auramusic.wiki.data.PublicWiki
import com.auramusic.wiki.ui.LocalNav
import com.auramusic.wiki.ui.components.AppTextField
import com.auramusic.wiki.ui.components.EmptyState
import com.auramusic.wiki.ui.components.ErrorState
import com.auramusic.wiki.ui.components.FlowRowCompat
import com.auramusic.wiki.ui.components.GradientButton
import com.auramusic.wiki.ui.components.InfoRow
import com.auramusic.wiki.ui.components.LocalToast
import com.auramusic.wiki.ui.components.PageHeader
import com.auramusic.wiki.ui.components.Pill
import com.auramusic.wiki.ui.components.RemoteImage
import com.auramusic.wiki.ui.components.SectionCard
import com.auramusic.wiki.ui.components.SkeletonList
import com.auramusic.wiki.ui.components.SoftButton
import com.auramusic.wiki.ui.components.enterAnimation
import com.auramusic.wiki.ui.theme.LocalBrand
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

class WikiViewModel(private val graph: AppGraph) : ViewModel() {
    var input by mutableStateOf("")
    var inputError by mutableStateOf<String?>(null)
    var status by mutableStateOf("输入歌曲 ID 即可查询，无需登录")
    var loading by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var result by mutableStateOf<JSONObject?>(null)
    var history by mutableStateOf(loadHistory())
    private var currentId: String? = null
    private var job: Job? = null

    private fun loadHistory(): List<Pair<String, String>> = runCatching {
        val array = JSONArray(graph.prefs.getString("history", "[]"))
        (0 until array.length()).mapNotNull { array.optJSONObject(it) }.map { it.optString("id") to it.optString("name") }
    }.getOrDefault(emptyList())

    private fun saveHistory(id: String, name: String) {
        val next = (listOf(id to name) + history.filter { it.first != id }).take(8)
        history = next
        val array = JSONArray()
        next.forEach { array.put(JSONObject().put("id", it.first).put("name", it.second)) }
        graph.prefs.edit().putString("history", array.toString()).apply()
    }

    fun query(text: String = input) {
        val short = PublicWiki.shortLink(text)
        val id = if (short == null) PublicWiki.normalizeId(text) else null
        if (id == null && short == null) {
            inputError = "请输入歌曲 ID、网易云歌曲链接或 163cn.tv 短链接"
            return
        }
        inputError = null
        if (id != null) input = id
        job?.cancel()
        currentId = id
        result = null
        error = null
        loading = true
        status = if (id == null) "正在解析短链接…" else "正在查询歌曲 $id…"
        job = viewModelScope.launch {
            try {
                val resolved = PublicWiki.resolveId(text)
                currentId = resolved
                input = resolved
                status = "正在查询歌曲 $resolved…"
                val json = PublicWiki.fetch(resolved)
                result = json
                status = "查询完成 · ID $resolved"
                saveHistory(resolved, json.optJSONObject("data")?.optString("songName", resolved) ?: resolved)
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                error = when (e) {
                    is SocketTimeoutException -> "查询超时，请检查网络后重试"
                    is UnknownHostException -> "无法连接服务器，请检查网络"
                    else -> e.message ?: "查询失败，请重试"
                }
                status = error.orEmpty()
            } finally {
                loading = false
            }
        }
    }

    fun refresh() {
        currentId?.let { input = it; query(it) }
    }
}

private fun JSONObject?.v(key: String): String =
    if (this == null || isNull(key)) "" else optString(key, "").trim()

private fun JSONArray?.joined(separator: String): String {
    if (this == null) return ""
    return (0 until length()).filter { !isNull(it) }.map { optString(it, "").trim() }.filter { it.isNotEmpty() }.joinToString(separator)
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun WikiScreen(graph: AppGraph) {
    val vm: WikiViewModel = viewModel { WikiViewModel(graph) }
    val nav = LocalNav.current
    val context = LocalContext.current
    val toast = LocalToast.current
    val focus = LocalFocusManager.current

    LaunchedEffect(nav.wikiRequest) {
        nav.wikiRequest?.let {
            vm.input = it.toString()
            vm.query(it.toString())
            nav.wikiRequest = null
        }
    }

    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 24.dp),
    ) {
        item(key = "header") {
            Box(Modifier.statusBarsPadding()) {
                PageHeader("歌曲百科", "查看歌曲资料、创作者和公开贡献记录") {
                    SoftButton("艺人资料", { nav.openArtistEditor() }, icon = Icons.Rounded.Person)
                }
            }
        }
        item(key = "search") {
            Column(Modifier.padding(horizontal = 20.dp).enterAnimation(0), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                AppTextField(
                    vm.input,
                    { vm.input = it; vm.inputError = null },
                    "歌曲 ID、分享链接或 163cn.tv 短链接",
                    leading = Icons.Rounded.Search,
                    error = vm.inputError,
                    imeAction = ImeAction.Search,
                    onIme = { focus.clearFocus(); vm.query() },
                    trailing = {
                        IconButton(onClick = {
                            val clip = (context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).primaryClip
                            if (clip == null || clip.itemCount == 0) toast("剪贴板为空")
                            else vm.input = clip.getItemAt(0).coerceToText(context)?.toString().orEmpty()
                        }) { Icon(Icons.Rounded.ContentPaste, "粘贴") }
                    },
                )
                GradientButton(
                    if (vm.loading) "查询中…" else "查询百科",
                    { focus.clearFocus(); vm.query() },
                    Modifier.fillMaxWidth(),
                    loading = vm.loading,
                    icon = Icons.Rounded.TravelExplore,
                )
            }
        }
        if (vm.history.isNotEmpty()) {
            item(key = "history") {
                LazyRow(
                    contentPadding = PaddingValues(horizontal = 20.dp, vertical = 12.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.animateItem(),
                ) {
                    items(vm.history, key = { it.first }) { (id, name) ->
                        AssistChip(
                            onClick = { vm.input = id; vm.query(id) },
                            label = { Text(name.ifBlank { id }, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.widthIn(max = IntrinsicWidthLimit)) },
                            leadingIcon = { Icon(Icons.Rounded.History, null, Modifier.size(16.dp)) },
                            shape = CircleShape,
                            colors = AssistChipDefaults.assistChipColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
                            modifier = Modifier.animateItem(),
                        )
                    }
                }
            }
        }
        item(key = "status") {
            AnimatedContent(vm.status, transitionSpec = { fadeIn(tween(200)) togetherWith fadeOut(tween(120)) }, label = "wikiStatus") {
                Text(
                    it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 24.dp, vertical = 4.dp),
                )
            }
        }
        item(key = "body") {
            val state = when {
                vm.loading -> 0
                vm.error != null -> 1
                vm.result != null -> 2
                else -> 3
            }
            AnimatedContent(
                state to vm.result,
                transitionSpec = { fadeIn(tween(320)) togetherWith fadeOut(tween(160)) },
                contentKey = { it.first },
                label = "wikiBody",
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            ) { (s, json) ->
                when (s) {
                    0 -> SkeletonList(3)
                    1 -> ErrorState(vm.error.orEmpty(), { vm.refresh() })
                    2 -> if (json != null) WikiResult(json, onRefresh = { vm.refresh() })
                    else -> EmptyState("输入歌曲 ID 或粘贴分享链接，查看歌曲百科", icon = Icons.Rounded.TravelExplore)
                }
            }
        }
        item(key = "footer") {
            Text(
                "数据来自云音乐歌曲百科公开记录",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { Links.browse(context, PublicWiki.HOME) }
                    .padding(vertical = 16.dp),
            )
        }
    }
}

private val IntrinsicWidthLimit = 140.dp

@Composable
private fun WikiResult(json: JSONObject, onRefresh: () -> Unit) {
    val context = LocalContext.current
    val toast = LocalToast.current
    val data = json.optJSONObject("data") ?: return
    val songId = data.v("songId")
    val wiki = data.optJSONObject("wiki")
    val ugc = data.optJSONObject("ugc")
    Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
        // 歌曲信息
        Box(
            Modifier
                .fillMaxWidth()
                .clip(MaterialTheme.shapes.large)
                .background(MaterialTheme.colorScheme.surfaceContainerLow)
                .enterAnimation(0),
        ) {
            Box(
                Modifier
                    .fillMaxWidth()
                    .height(120.dp)
                    .background(
                        Brush.verticalGradient(
                            listOf(MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.surfaceContainerLow),
                        ),
                    ),
            )
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RemoteImage(
                        PublicWiki.thumbnail(data.v("coverUrl"), 256),
                        data.v("songName") + "封面",
                        Modifier.size(96.dp),
                        RoundedCornerShape(20.dp),
                        fallback = data.v("songName"),
                    )
                    Spacer(Modifier.width(16.dp))
                    Column(Modifier.weight(1f)) {
                        androidx.compose.foundation.text.selection.SelectionContainer {
                            Text(data.v("songName").ifBlank { "未知歌曲" }, style = MaterialTheme.typography.headlineSmall)
                        }
                        Spacer(Modifier.height(4.dp))
                        Text(
                            data.optJSONArray("artistName").joined(" / "),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(8.dp))
                        Pill("ID $songId")
                    }
                }
                ugc.v("transName").takeIf { it.isNotEmpty() }?.let {
                    Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    InfoRow("语种", wiki.v("language"))
                    InfoRow("BPM", wiki.v("bpm"))
                    InfoRow("时长", ugc.v("duration"))
                    InfoRow("发行日期", wiki.v("releaseDate"))
                    InfoRow("版本", wiki.v("releaseVersion"))
                    InfoRow("原唱类型", ugc.v("coverType"))
                    InfoRow("曲风", wiki?.optJSONArray("genres").joined(" · "))
                    InfoRow("情绪标签", wiki?.optJSONArray("moods").joined(" · "))
                    InfoRow("相关作品", wiki?.optJSONArray("entertainment").joined("\n"))
                    InfoRow("审核标签", ugc?.optJSONArray("reviewTags").joined(" · "))
                    InfoRow("锁定项目", ugc?.optJSONArray("locks").joined(" · "))
                }
                SoftButton(
                    "在网易云查看歌曲",
                    { Links.open(context, "https://music.163.com/song?id=$songId") },
                    Modifier.fillMaxWidth(),
                    icon = Icons.AutoMirrored.Rounded.OpenInNew,
                )
            }
        }

        // 创作者
        SectionCard("创作者", Modifier.enterAnimation(1)) {
            val creators = wiki?.optJSONArray("creators")
            var count = 0
            if (creators != null) {
                for (i in 0 until creators.length()) {
                    val group = creators.optJSONObject(i) ?: continue
                    val people = group.optJSONArray("people") ?: continue
                    if (people.length() == 0) continue
                    Text(group.v("role"), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    FlowRowCompat {
                        for (j in 0 until people.length()) {
                            val person = people.optJSONObject(j) ?: continue
                            val name = person.v("name")
                            if (name.isEmpty()) continue
                            count++
                            val artistId = person.v("artistId")
                            if (artistId.matches(Regex("[1-9][0-9]{0,19}"))) {
                                Pill(
                                    name,
                                    Modifier.clip(CircleShape).clickable { Links.open(context, "https://music.163.com/artist?id=$artistId") },
                                    color = MaterialTheme.colorScheme.primaryContainer,
                                    contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                                )
                            } else {
                                Pill(name, color = MaterialTheme.colorScheme.surfaceContainerHigh, contentColor = MaterialTheme.colorScheme.onSurface)
                            }
                        }
                    }
                }
            }
            if (count == 0) Text("暂无公开创作者信息", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }

        // 贡献记录
        val records = data.optJSONArray("records").let { array ->
            if (array == null) emptyList() else (0 until array.length()).mapNotNull { array.optJSONObject(it) }
        }.sortedByDescending { it.optLong("createTime") }
        Text(
            "贡献记录 · ${records.size}",
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(start = 6.dp, top = 6.dp),
        )
        if (records.isEmpty()) {
            EmptyState("这首歌暂无公开贡献记录")
        } else {
            val format = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.CHINA)
            records.forEachIndexed { index, record -> RecordCard(record, format, index) }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            SoftButton(
                "复制查询数据",
                {
                    (context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager)
                        .setPrimaryClip(ClipData.newPlainText("歌曲百科 JSON", json.toString()))
                    toast("已复制完整 JSON 数据")
                },
                Modifier.weight(1f),
                icon = Icons.Rounded.ContentCopy,
            )
            SoftButton("刷新", onRefresh, icon = Icons.Rounded.Refresh)
        }
    }
}

@Composable
private fun RecordCard(record: JSONObject, format: SimpleDateFormat, index: Int) {
    val context = LocalContext.current
    val name = record.v("nickName").ifEmpty { "匿名贡献者" }
    val userId = record.v("userId")
    val open = if (userId.matches(Regex("[1-9][0-9]{0,19}"))) {
        { Links.open(context, "https://music.163.com/user/home?id=$userId") }
    } else {
        null
    }
    val time = record.optLong("createTime", 0L)
    Column(
        Modifier
            .fillMaxWidth()
            .enterAnimation(index + 2, record.optLong("createTime"))
            .clip(MaterialTheme.shapes.large)
            .background(MaterialTheme.colorScheme.surfaceContainerLow)
            .then(if (open != null) Modifier.clickable(onClick = open) else Modifier)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            RemoteImage(
                PublicWiki.thumbnail(record.v("userImg"), 128),
                "${name}的头像",
                Modifier.size(42.dp),
                CircleShape,
                fallback = name,
            )
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(name, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                Text(
                    if (time > 0) format.format(Date(time)) else "时间未知",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Text(
            record.optJSONArray("approveNames").joined(" · ").ifEmpty { "其他贡献" },
            style = MaterialTheme.typography.bodyMedium,
            color = LocalBrand.current.glow,
        )
        if (userId.isNotEmpty()) {
            Text("用户 ID $userId", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
