package com.auramusic.wiki.ui.screens

import androidx.compose.animation.core.animateIntAsState
import androidx.compose.animation.core.tween
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Logout
import androidx.compose.material.icons.automirrored.rounded.OpenInNew
import androidx.compose.material.icons.rounded.Person
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.auramusic.wiki.AppGraph
import com.auramusic.wiki.ui.LocalBottomBarSpace
import com.auramusic.wiki.data.Channel
import com.auramusic.wiki.data.Contribution
import com.auramusic.wiki.data.Devote
import com.auramusic.wiki.data.Links
import com.auramusic.wiki.data.Page
import com.auramusic.wiki.data.WikiApi
import com.auramusic.wiki.ui.components.EmptyState
import com.auramusic.wiki.ui.components.ErrorState
import com.auramusic.wiki.ui.components.Pager
import com.auramusic.wiki.ui.components.RemoteImage
import com.auramusic.wiki.ui.components.SectionCard
import com.auramusic.wiki.ui.components.SkeletonList
import com.auramusic.wiki.ui.components.SoftButton
import com.auramusic.wiki.ui.components.StatusPill
import com.auramusic.wiki.ui.components.Tone
import com.auramusic.wiki.ui.components.enterAnimation
import com.auramusic.wiki.ui.theme.LocalBrand
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

private val CONTRIB_TYPES = listOf("补充专辑" to 101, "歌曲" to 3, "专辑" to 2, "艺人" to 1, "MV" to 4, "补充MV" to 103)
private val CONTRIB_STATUS: List<Pair<String, Int?>> = listOf<Pair<String, Int?>>("全部" to null) + WikiApi.AUDIT_STATUS.map { it.value to it.key }
private const val CONTRIB_PAGE = 10

class MineViewModel(private val graph: AppGraph) : ViewModel() {
    var devote by mutableStateOf<Devote?>(null)
    var type by mutableIntStateOf(0)
    var status by mutableIntStateOf(0)
    var page by mutableIntStateOf(0)
    var list by mutableStateOf<Page<Contribution>?>(null)
    var loading by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    private var job: Job? = null

    fun loadDevote() {
        viewModelScope.launch { runCatching { graph.api.devote() }.onSuccess { devote = it } }
    }

    fun load() {
        job?.cancel()
        loading = true
        error = null
        job = viewModelScope.launch {
            try {
                list = graph.api.contributions(CONTRIB_TYPES[type].second, CONTRIB_STATUS[status].second, page * CONTRIB_PAGE, CONTRIB_PAGE)
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                error = e.message ?: "加载失败"
                list = null
            } finally {
                loading = false
            }
        }
    }
}

@Composable
fun MineScreen(graph: AppGraph) {
    val vm: MineViewModel = viewModel { MineViewModel(graph) }
    val account by graph.session.account.collectAsState()
    val channel by graph.session.channel.collectAsState()
    val context = LocalContext.current
    var confirmLogout by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { vm.loadDevote() }
    LaunchedEffect(vm.type, vm.status, vm.page) { vm.load() }

    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 24.dp + LocalBottomBarSpace.current), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item(key = "profile") {
            Column(
                Modifier
                    .statusBarsPadding()
                    .padding(top = 12.dp)
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(30.dp))
                    .background(LocalBrand.current.gradient)
                    .padding(20.dp)
                    .enterAnimation(0),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(68.dp).clip(CircleShape).background(Color.White.copy(alpha = 0.3f)).padding(3.dp)) {
                        RemoteImage(account?.avatarUrl, "头像", Modifier.fillMaxSize(), CircleShape, fallback = account?.nickname ?: "我")
                    }
                    Spacer(Modifier.width(16.dp))
                    Column(Modifier.weight(1f)) {
                        Text(account?.nickname ?: "已登录", style = MaterialTheme.typography.headlineSmall, color = Color.White, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(
                            account?.let { "用户 ID ${it.userId}" } ?: "网易云账号",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color.White.copy(alpha = 0.85f),
                        )
                    }
                    Box(
                        Modifier.clip(CircleShape).background(Color.White.copy(alpha = 0.2f)).clickable { confirmLogout = true }.padding(10.dp),
                    ) { Icon(Icons.AutoMirrored.Rounded.Logout, "退出", tint = Color.White) }
                }
                Spacer(Modifier.height(18.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Stat("贡献", vm.devote?.ugcCount, Modifier.weight(1f))
                    Stat("积分", vm.devote?.cloudShell, Modifier.weight(1f))
                }
            }
        }
        item(key = "contribHeader") {
            SectionCard("我的贡献", Modifier.enterAnimation(1)) {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    itemsIndexed(CONTRIB_TYPES) { index, (label, _) ->
                        FilterChip(selected = vm.type == index, onClick = { vm.type = index; vm.page = 0 }, label = { Text(label) })
                    }
                }
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    itemsIndexed(CONTRIB_STATUS) { index, (label, _) ->
                        FilterChip(selected = vm.status == index, onClick = { vm.status = index; vm.page = 0 }, label = { Text(label) })
                    }
                }
            }
        }
        val list = vm.list
        when {
            vm.loading && list == null -> item(key = "loading") { SkeletonList(3) }
            vm.error != null && list == null -> item(key = "error") { ErrorState(vm.error.orEmpty(), { vm.load() }) }
            list == null || list.items.isEmpty() -> item(key = "empty") { EmptyState("还没有记录") }
            else -> {
                itemsIndexed(list.items, key = { i, c -> "${c.bizId}-${c.createTime}-$i" }) { index, item ->
                    ContributionCard(item, Modifier.animateItem().enterAnimation(index, "${vm.type}-${vm.status}-${vm.page}-${item.bizId}"))
                }
                item(key = "pager") {
                    val pages = (list.total + CONTRIB_PAGE - 1) / CONTRIB_PAGE
                    Pager(vm.page, pages, { vm.page = it }, "共 ${list.total} 条 · 第 ${vm.page + 1} 页")
                }
            }
        }
        item(key = "web") {
            SoftButton(
                "在网页版查看全部贡献",
                { Links.browse(context, "https://music.163.com/#/wiki/contribution") },
                Modifier.fillMaxWidth(),
                icon = Icons.AutoMirrored.Rounded.OpenInNew,
            )
        }
        item(key = "channel") {
            SectionCard(
                "接口通道",
                Modifier.enterAnimation(3),
                subtitle = "自动：先用 App 的 eapi，失败时改用网页版 weapi（网页百科本身使用的方式）。",
                trailing = { Icon(Icons.Rounded.Tune, null, tint = MaterialTheme.colorScheme.onSurfaceVariant) },
            ) {
                Channel.entries.forEach { option ->
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(14.dp))
                            .clickable { graph.session.setChannel(option) }
                            .padding(vertical = 2.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RadioButton(channel == option, { graph.session.setChannel(option) })
                        Text(option.label, style = MaterialTheme.typography.bodyLarge)
                    }
                }
            }
        }
    }

    if (confirmLogout) {
        AlertDialog(
            onDismissRequest = { confirmLogout = false },
            icon = { Icon(Icons.Rounded.Person, null) },
            title = { Text("退出登录") },
            text = { Text("退出后需要重新登录才能提交资料。") },
            confirmButton = { TextButton(onClick = { confirmLogout = false; graph.session.logout() }) { Text("退出") } },
            dismissButton = { TextButton(onClick = { confirmLogout = false }) { Text("取消") } },
        )
    }
}

@Composable
private fun Stat(label: String, value: Int?, modifier: Modifier) {
    val animated by animateIntAsState(value ?: 0, tween(900), label = "stat")
    Column(
        modifier
            .clip(RoundedCornerShape(20.dp))
            .background(Color.White.copy(alpha = 0.18f))
            .padding(horizontal = 16.dp, vertical = 12.dp),
    ) {
        Text(if (value == null) "—" else animated.toString(), style = MaterialTheme.typography.headlineSmall, color = Color.White)
        Text(label, style = MaterialTheme.typography.labelMedium, color = Color.White.copy(alpha = 0.85f))
    }
}

@Composable
private fun ContributionCard(item: Contribution, modifier: Modifier) {
    val label = WikiApi.AUDIT_STATUS[item.status]
    val tone = when (item.status) {
        5 -> Tone.Success
        4 -> Tone.Info
        -5 -> Tone.Danger
        1 -> Tone.Warning
        else -> Tone.Neutral
    }
    Column(
        modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.large)
            .background(MaterialTheme.colorScheme.surfaceContainerLow)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(item.name.ifBlank { "未命名" }, style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (label != null) StatusPill(label, tone)
        }
        if (item.artists.isNotBlank()) {
            Text(item.artists, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (item.createTime > 0) {
            Text(
                SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.CHINA).format(Date(item.createTime)),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (item.approved.isNotEmpty()) {
            Text("通过：" + item.approved.joinToString("、"), style = MaterialTheme.typography.bodySmall, color = LocalBrand.current.success)
        }
        if (item.rejected.isNotEmpty()) {
            Text("未通过：" + item.rejected.joinToString("、"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
        }
    }
}
