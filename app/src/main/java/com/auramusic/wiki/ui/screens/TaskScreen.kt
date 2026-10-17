package com.auramusic.wiki.ui.screens

import android.content.Context
import androidx.activity.compose.BackHandler
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
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Assignment
import androidx.compose.material.icons.rounded.Groups
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Whatshot
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.PrimaryScrollableTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRowDefaults
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.auramusic.wiki.AppGraph
import com.auramusic.wiki.ui.LocalBottomBarSpace
import com.auramusic.wiki.data.Links
import com.auramusic.wiki.data.Page
import com.auramusic.wiki.data.Recommend
import com.auramusic.wiki.data.TaskGroup
import com.auramusic.wiki.data.TaskInfo
import com.auramusic.wiki.data.TaskItem
import com.auramusic.wiki.data.WikiApi
import com.auramusic.wiki.ui.AppNav
import com.auramusic.wiki.ui.LocalNav
import com.auramusic.wiki.ui.components.AppTextField
import com.auramusic.wiki.ui.components.EmptyState
import com.auramusic.wiki.ui.components.ErrorState
import com.auramusic.wiki.ui.components.FlowRowCompat
import com.auramusic.wiki.ui.components.GradientButton
import com.auramusic.wiki.ui.components.LocalToast
import com.auramusic.wiki.ui.components.PageHeader
import com.auramusic.wiki.ui.components.Pager
import com.auramusic.wiki.ui.components.RemoteImage
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

private val TABS = listOf("推荐" to 0, "歌曲" to 3, "专辑" to 2, "艺人" to 1, "MV" to 4, "歌词" to 5, "我的" to -1)
private val MY_TYPES = listOf("歌曲" to 3, "专辑" to 2, "艺人" to 1, "MV" to 4)
private val MY_STATUS = listOf<Pair<String, Int?>>("全部" to null, "进行中" to 0, "审核中" to 20, "已完成" to 100, "未通过" to 30, "已过期" to -1)
private val TASK_LANGUAGES = listOf<String?>(null, "国语", "粤语", "英语", "日语", "韩语", "其他")
private const val PAGE_SIZE = 20

class Loadable<T> {
    var data by mutableStateOf<T?>(null)
    var loading by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
}

class TaskViewModel(private val graph: AppGraph) : ViewModel() {
    var tab by mutableIntStateOf(0)
    val recommend = Loadable<List<Recommend>>()
    val groups = mutableStateMapOf<Int, Loadable<List<TaskGroup>>>()
    var group by mutableStateOf<Pair<TaskGroup, Int>?>(null)
    val info = Loadable<TaskInfo>()
    val items = Loadable<Page<TaskItem>>()
    var query by mutableStateOf("")
    var language by mutableStateOf<String?>(null)
    var page by mutableIntStateOf(0)
    var myType by mutableIntStateOf(3)
    var myStatus by mutableStateOf<Int?>(null)
    var myPage by mutableIntStateOf(0)
    val mine = Loadable<Page<TaskItem>>()
    val claimed = mutableStateMapOf<String, Boolean>()
    var claiming by mutableStateOf<String?>(null)
    private var itemsJob: Job? = null
    private var mineJob: Job? = null

    private fun <T> load(target: Loadable<T>, block: suspend () -> T): Job {
        target.loading = true
        target.error = null
        return viewModelScope.launch {
            try {
                target.data = block()
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                target.error = e.message ?: "加载失败"
            } finally {
                target.loading = false
            }
        }
    }

    fun loadRecommend(force: Boolean = false) {
        if (!force && (recommend.data != null || recommend.loading)) return
        load(recommend) { graph.api.recommendTasks() }
    }

    fun groupsOf(type: Int): Loadable<List<TaskGroup>> = groups.getOrPut(type) { Loadable() }

    fun loadGroups(type: Int, force: Boolean = false) {
        val target = groupsOf(type)
        if (!force && (target.data != null || target.loading)) return
        load(target) { graph.api.taskGroups(type) }
    }

    fun openGroup(group: TaskGroup, type: Int) {
        this.group = group to type
        query = ""
        language = null
        page = 0
        info.data = null
        items.data = null
        load(info) { graph.api.taskInfo(group.missionId) }
        loadItems()
    }

    fun loadItems() {
        val (g, type) = group ?: return
        itemsJob?.cancel()
        itemsJob = load(items) { graph.api.taskItems(g.missionId, type, query.trim(), language, page * PAGE_SIZE, PAGE_SIZE) }
    }

    fun loadMine() {
        mineJob?.cancel()
        mineJob = load(mine) { graph.api.myTasks(myType, myStatus, myPage * PAGE_SIZE, PAGE_SIZE) }
    }

    fun claim(item: TaskItem, onToast: (String) -> Unit) {
        val key = "${item.missionId}-${item.resId}"
        claiming = key
        viewModelScope.launch {
            try {
                graph.api.claimTask(item)
                claimed[key] = true
                onToast("认领成功")
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                onToast(e.message ?: "认领失败")
            } finally {
                claiming = null
            }
        }
    }
}

/** 去完成：歌曲类跳到应用内编辑，其余打开网页版。 */
private fun complete(item: TaskItem, nav: AppNav, context: Context) {
    val type = if (item.resType == 5 || item.resType == 6) 3 else item.resType
    if (type == 3) {
        nav.openSong(item.resId)
    } else {
        val path = WikiApi.TASK_LINK_TYPES[type] ?: "song"
        val actions = if (item.subAction.isNotBlank()) "&actions=${item.subAction}" else ""
        Links.browse(context, "https://music.163.com/#/wiki/$path?${path}Id=${item.resId}$actions")
    }
}

@Composable
fun TaskScreen(graph: AppGraph) {
    val vm: TaskViewModel = viewModel { TaskViewModel(graph) }
    BackHandler(enabled = vm.group != null) { vm.group = null }
    AnimatedContent(
        vm.group,
        transitionSpec = {
            val dir = if (targetState != null) 1 else -1
            (slideInHorizontally(tween(360, easing = FastOutSlowInEasing)) { it / 3 * dir } + fadeIn(tween(300)))
                .togetherWith(slideOutHorizontally(tween(300, easing = FastOutSlowInEasing)) { -it / 4 * dir } + fadeOut(tween(200)))
        },
        contentKey = { it?.first?.missionId },
        label = "taskNav",
    ) { selected ->
        if (selected == null) TaskHome(vm) else TaskDetail(vm, selected.first, selected.second)
    }
}

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
private fun TaskHome(vm: TaskViewModel) {
    Column(Modifier.fillMaxSize()) {
        Box(Modifier.statusBarsPadding()) { PageHeader("云小编任务中心", "领取任务、补充资料，赚取云贝积分") }
        PrimaryScrollableTabRow(
            selectedTabIndex = vm.tab,
            edgePadding = 16.dp,
            containerColor = MaterialTheme.colorScheme.background,
            divider = {},
            indicator = {
                TabRowDefaults.PrimaryIndicator(
                    Modifier.tabIndicatorOffset(vm.tab, matchContentSize = true),
                    width = androidx.compose.ui.unit.Dp.Unspecified,
                    shape = RoundedCornerShape(3.dp),
                )
            },
        ) {
            TABS.forEachIndexed { index, (label, _) ->
                Tab(
                    selected = vm.tab == index,
                    onClick = { vm.tab = index },
                    text = { Text(label, style = MaterialTheme.typography.titleSmall) },
                    selectedContentColor = MaterialTheme.colorScheme.primary,
                    unselectedContentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        AnimatedContent(
            vm.tab,
            transitionSpec = {
                val dir = if (targetState > initialState) 1 else -1
                (slideInHorizontally(tween(300)) { it / 6 * dir } + fadeIn(tween(260)))
                    .togetherWith(slideOutHorizontally(tween(260)) { -it / 8 * dir } + fadeOut(tween(160)))
            },
            label = "taskTab",
            modifier = Modifier.weight(1f),
        ) { index ->
            val type = TABS[index].second
            when (type) {
                0 -> RecommendTab(vm)
                -1 -> MyTasksTab(vm)
                else -> GroupsTab(vm, type)
            }
        }
    }
}

@Composable
private fun RecommendTab(vm: TaskViewModel) {
    LaunchedEffect(Unit) { vm.loadRecommend() }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = 16.dp, top = 16.dp, end = 16.dp, bottom = 16.dp + LocalBottomBarSpace.current), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        stateItems(vm.recommend, { vm.loadRecommend(true) }, "暂时没有推荐任务") { list ->
            list.forEachIndexed { index, rec ->
                item(key = "rec-${rec.group.missionId}-$index") {
                    Column(
                        Modifier
                            .animateItem()
                            .enterAnimation(index, rec.group.missionId)
                            .fillMaxWidth()
                            .clip(MaterialTheme.shapes.large)
                            .background(MaterialTheme.colorScheme.surfaceContainerLow)
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        GroupHeader(rec.group, onClick = { vm.openGroup(rec.group, rec.type) })
                        rec.items.forEach { TaskRow(vm, it) }
                    }
                }
            }
        }
    }
}

@Composable
private fun GroupsTab(vm: TaskViewModel, type: Int) {
    LaunchedEffect(type) { vm.loadGroups(type) }
    val target = vm.groupsOf(type)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = 16.dp, top = 16.dp, end = 16.dp, bottom = 16.dp + LocalBottomBarSpace.current), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        stateItems(target, { vm.loadGroups(type, true) }, "没有任务") { list ->
            itemsIndexed(list, key = { i, g -> "${g.missionId}-$i" }) { index, group ->
                Box(
                    Modifier
                        .animateItem()
                        .enterAnimation(index, group.missionId)
                        .fillMaxWidth()
                        .clip(MaterialTheme.shapes.large)
                        .background(MaterialTheme.colorScheme.surfaceContainerLow)
                        .clickable { vm.openGroup(group, type) }
                        .padding(14.dp),
                ) { GroupHeader(group, null) }
            }
        }
    }
}

@Composable
private fun GroupHeader(group: TaskGroup, onClick: (() -> Unit)?) {
    Row(
        Modifier.fillMaxWidth().then(if (onClick != null) Modifier.clip(RoundedCornerShape(14.dp)).clickable(onClick = onClick) else Modifier),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RemoteImage(group.picUrl, null, Modifier.size(56.dp), RoundedCornerShape(16.dp), fallback = group.name)
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Text(group.name, style = MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Spacer(Modifier.height(4.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Rounded.Groups, null, Modifier.size(14.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.width(4.dp))
                Text(
                    "${group.resCount} 个资源 · ${group.userCount} 人参与",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun TaskRow(vm: TaskViewModel, item: TaskItem, forceComplete: Boolean = false) {
    val nav = LocalNav.current
    val context = LocalContext.current
    val toast = LocalToast.current
    val key = "${item.missionId}-${item.resId}"
    val done = forceComplete || vm.claimed[key] == true
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(MaterialTheme.colorScheme.surfaceContainer.copy(alpha = 0.6f))
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(item.resName.ifBlank { "未命名" }, style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (item.artistName.isNotBlank()) {
                Text(item.artistName, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
            }
            FlowRowCompat(spacing = 6.dp) {
                if (item.reward.isNotBlank()) StatusPill("奖励 ${item.reward} 积分", Tone.Warning)
                if (item.heat.isNotBlank()) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Rounded.Whatshot, null, Modifier.size(14.dp), tint = LocalBrand.current.glow)
                        Text("热度 ${item.heat}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                item.status?.let { status ->
                    val label = WikiApi.TASK_STATUS[status]
                    if (label != null) StatusPill("状态 $label", toneOf(status))
                }
                item.deadline?.let {
                    Text(
                        "截止 " + SimpleDateFormat("MM-dd HH:mm", Locale.CHINA).format(Date(it)),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        Spacer(Modifier.width(10.dp))
        AnimatedContent(done, transitionSpec = { fadeIn(tween(220)) togetherWith fadeOut(tween(120)) }, label = "claim") { finished ->
            if (finished) {
                SoftButton("去完成", { complete(item, nav, context) })
            } else {
                GradientButton("认领", { vm.claim(item, toast) }, loading = vm.claiming == key)
            }
        }
    }
}

private fun toneOf(status: Int) = when (status) {
    100 -> Tone.Success
    20 -> Tone.Info
    30 -> Tone.Danger
    -1 -> Tone.Neutral
    else -> Tone.Warning
}

@Composable
private fun TaskDetail(vm: TaskViewModel, group: TaskGroup, type: Int) {
    val focus = LocalFocusManager.current
    val context = LocalContext.current
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 24.dp + LocalBottomBarSpace.current), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item(key = "header") {
            Box(Modifier.statusBarsPadding()) { PageHeader(group.name, onBack = { vm.group = null }) }
        }
        item(key = "info") {
            Column(
                Modifier
                    .fillMaxWidth()
                    .clip(MaterialTheme.shapes.large)
                    .background(LocalBrand.current.gradient)
                    .padding(18.dp)
                    .enterAnimation(0),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                val info = vm.info.data
                Text(info?.name?.ifBlank { null } ?: group.name, style = MaterialTheme.typography.titleLarge, color = androidx.compose.ui.graphics.Color.White)
                if (!info?.desc.isNullOrBlank()) {
                    Text(info?.desc.orEmpty(), style = MaterialTheme.typography.bodyMedium, color = androidx.compose.ui.graphics.Color.White.copy(alpha = 0.9f))
                }
                Text(
                    "${info?.resCount ?: group.resCount} 个资源 · ${info?.userCount ?: group.userCount} 人参与",
                    style = MaterialTheme.typography.labelLarge,
                    color = androidx.compose.ui.graphics.Color.White,
                )
                group.url?.let { url ->
                    Text(
                        "打开活动页",
                        style = MaterialTheme.typography.labelLarge,
                        color = androidx.compose.ui.graphics.Color.White,
                        modifier = Modifier.clip(RoundedCornerShape(10.dp)).clickable { Links.browse(context, url) }.padding(vertical = 4.dp),
                    )
                }
            }
        }
        item(key = "filter") {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                AppTextField(
                    vm.query, { vm.query = it }, "搜索歌名/歌手/专辑",
                    leading = Icons.Rounded.Search,
                    imeAction = ImeAction.Search,
                    onIme = { focus.clearFocus(); vm.page = 0; vm.loadItems() },
                )
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    itemsIndexed(TASK_LANGUAGES) { _, language ->
                        FilterChip(
                            selected = vm.language == language,
                            onClick = { vm.language = language; vm.page = 0; vm.loadItems() },
                            label = { Text(language ?: "全部语种") },
                            colors = FilterChipDefaults.filterChipColors(selectedContainerColor = MaterialTheme.colorScheme.primaryContainer),
                        )
                    }
                }
            }
        }
        val items = vm.items
        stateItems(items, { vm.loadItems() }, "没有符合条件的资源") { page ->
            item(key = "count") {
                Text("共 ${page.total} 个任务", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            itemsIndexed(page.items, key = { i, it -> "${it.resId}-$i" }) { index, task ->
                Box(Modifier.animateItem().enterAnimation(index, task.resId)) { TaskRow(vm, task) }
            }
            item(key = "pager") {
                val pages = (page.total + PAGE_SIZE - 1) / PAGE_SIZE
                Pager(vm.page, pages, { vm.page = it; vm.loadItems() })
            }
        }
    }
}

@Composable
private fun MyTasksTab(vm: TaskViewModel) {
    LaunchedEffect(vm.myType, vm.myStatus, vm.myPage) { vm.loadMine() }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = 16.dp, top = 16.dp, end = 16.dp, bottom = 16.dp + LocalBottomBarSpace.current), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item(key = "filters") {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    itemsIndexed(MY_TYPES) { _, (label, value) ->
                        FilterChip(selected = vm.myType == value, onClick = { vm.myType = value; vm.myPage = 0 }, label = { Text(label) })
                    }
                }
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    itemsIndexed(MY_STATUS) { _, (label, value) ->
                        FilterChip(selected = vm.myStatus == value, onClick = { vm.myStatus = value; vm.myPage = 0 }, label = { Text(label) })
                    }
                }
            }
        }
        stateItems(vm.mine, { vm.loadMine() }, "暂时没有这类任务") { page ->
            itemsIndexed(page.items, key = { i, it -> "${it.missionId}-${it.resId}-$i" }) { index, task ->
                Box(Modifier.animateItem().enterAnimation(index, task.resId)) { TaskRow(vm, task, forceComplete = true) }
            }
            item(key = "pager") {
                val pages = (page.total + PAGE_SIZE - 1) / PAGE_SIZE
                Pager(vm.myPage, pages, { vm.myPage = it }, "共 ${page.total} 个任务 · 第 ${vm.myPage + 1} 页")
            }
        }
    }
}

/** 列表内的加载 / 错误 / 空 状态。 */
private fun <T> LazyListScope.stateItems(
    target: Loadable<T>,
    retry: () -> Unit,
    emptyText: String,
    content: LazyListScope.(T) -> Unit,
) {
    val data = target.data
    when {
        target.loading && data == null -> item(key = "loading") { SkeletonList(4) }
        target.error != null && data == null -> item(key = "error") { ErrorState(target.error.orEmpty(), retry) }
        data == null -> Unit
        data is List<*> && data.isEmpty() -> item(key = "empty") { EmptyState(emptyText, icon = Icons.AutoMirrored.Rounded.Assignment) }
        data is Page<*> && data.items.isEmpty() -> item(key = "empty") { EmptyState(emptyText, icon = Icons.AutoMirrored.Rounded.Assignment) }
        else -> content(data)
    }
}

