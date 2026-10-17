package com.auramusic.wiki.ui.components

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.PersonAdd
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import com.auramusic.wiki.data.WikiArtist
import com.auramusic.wiki.data.WikiTag
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Sheet(title: String, onDismiss: () -> Unit, content: @Composable () -> Unit) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp)
                .navigationBarsPadding()
                .padding(bottom = 16.dp),
        ) {
            Text(title, style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.size(12.dp))
            content()
        }
    }
}

/** 搜索并选择艺人，找不到时可作为新艺人添加。 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun ArtistPickerSheet(
    search: suspend (String) -> List<WikiArtist>,
    onPick: (WikiArtist) -> Unit,
    onDismiss: () -> Unit,
    allowNew: Boolean = true,
    title: String = "选择艺人",
) {
    var query by remember { mutableStateOf("") }
    var results by remember { mutableStateOf<List<WikiArtist>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(query) {
        val text = query.trim()
        if (text.isEmpty()) {
            results = emptyList()
            error = null
            return@LaunchedEffect
        }
        delay(350)
        loading = true
        val result = runCatching { search(text) }
        loading = false
        results = result.getOrDefault(emptyList())
        error = result.exceptionOrNull()?.message
    }
    Sheet(title, onDismiss) {
        AppTextField(
            query, { query = it }, "艺人名或艺人 ID",
            leading = Icons.Rounded.Search, imeAction = ImeAction.Search,
            trailing = { if (loading) androidx.compose.material3.CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp) },
        )
        Spacer(Modifier.size(8.dp))
        LazyColumn(Modifier.heightIn(max = 460.dp)) {
            if (allowNew && query.isNotBlank()) {
                item(key = "new") {
                    ListItem(
                        headlineContent = { Text("无匹配结果？直接添加「${query.trim()}」") },
                        supportingContent = { Text("作为新艺人提交，由审核人员建档") },
                        leadingContent = { Icon(Icons.Rounded.PersonAdd, null, tint = MaterialTheme.colorScheme.primary) },
                        colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
                        modifier = Modifier
                            .animateItem()
                            .clickableRow { onPick(WikiArtist(null, query.trim())) },
                    )
                }
            }
            if (error != null) item(key = "error") { Hint(error.orEmpty()) }
            itemsIndexed(results, key = { i, a -> "${a.id}-$i" }) { index, artist ->
                ListItem(
                    headlineContent = { Text(artist.name) },
                    supportingContent = { Text("ID ${artist.id}") },
                    leadingContent = {
                        RemoteImage(artist.avatarUrl, null, Modifier.size(44.dp), CircleShape, fallback = artist.name)
                    },
                    colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
                    modifier = Modifier
                        .animateItem()
                        .enterAnimation(index, artist.id)
                        .clickableRow { onPick(artist) },
                )
            }
        }
    }
}

private val RowShape = androidx.compose.foundation.shape.RoundedCornerShape(16.dp)

private fun Modifier.clickableRow(onClick: () -> Unit) = this.clip(RowShape).clickable(onClick = onClick)

/** 多选语种：「未知」「其他」「纯音乐」只能单独选择。 */
@Composable
fun LanguagePickerSheet(
    options: List<String>,
    exclusive: Set<String>,
    selected: List<String>,
    onDone: (List<String>) -> Unit,
    onDismiss: () -> Unit,
) {
    val picked = remember { mutableStateListOf<String>().apply { addAll(selected) } }
    Sheet("语种", onDismiss) {
        Hint("「未知」「其他」「纯音乐」只能单独选择")
        Spacer(Modifier.size(12.dp))
        Column(Modifier.heightIn(max = 420.dp).androidxVerticalScroll()) {
            FlowRowCompat {
                options.forEach { language ->
                    val on = language in picked
                    FilterChip(
                        selected = on,
                        onClick = {
                            if (on) {
                                picked.remove(language)
                            } else if (language in exclusive) {
                                picked.clear(); picked.add(language)
                            } else {
                                picked.removeAll { it in exclusive }; picked.add(language)
                            }
                        },
                        label = { Text(language) },
                        leadingIcon = if (on) ({ Icon(Icons.Rounded.Check, null, Modifier.size(16.dp)) }) else null,
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = MaterialTheme.colorScheme.primaryContainer,
                        ),
                    )
                }
            }
        }
        Spacer(Modifier.size(16.dp))
        GradientButton("确定 · 已选 ${picked.size}", { onDone(picked.toList()) }, Modifier.fillMaxWidth())
    }
}

@Composable
private fun Modifier.androidxVerticalScroll(): Modifier = this.verticalScroll(rememberScrollState())

/** 曲风：搜索后多选，最多 3 个。 */
@Composable
fun TagPickerSheet(
    search: suspend (String) -> List<WikiTag>,
    selected: List<WikiTag>,
    onDone: (List<WikiTag>) -> Unit,
    onDismiss: () -> Unit,
) {
    val picked = remember { mutableStateListOf<WikiTag>().apply { addAll(selected) } }
    var query by remember { mutableStateOf("") }
    var results by remember { mutableStateOf<List<WikiTag>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    LaunchedEffect(query) {
        delay(300)
        loading = true
        results = runCatching { search(query.trim()) }.getOrDefault(emptyList())
        loading = false
    }
    Sheet("曲风（最多 3 个）", onDismiss) {
        AppTextField(query, { query = it }, "搜索曲风", leading = Icons.Rounded.Search)
        Spacer(Modifier.size(10.dp))
        Reveal(picked.isNotEmpty()) {
            Column {
                FlowRowCompat {
                    picked.forEach { tag -> Pill(tag.name, onRemove = { picked.remove(tag) }) }
                }
                Spacer(Modifier.size(10.dp))
            }
        }
        AnimatedContent(loading && results.isEmpty(), transitionSpec = { fadeIn(tween(200)) togetherWith fadeOut(tween(120)) }, label = "tags") { busy ->
            if (busy) {
                SkeletonList(3)
            } else {
                Column(Modifier.heightIn(max = 360.dp).androidxVerticalScroll()) {
                    FlowRowCompat {
                        results.forEach { tag ->
                            val on = picked.any { it.id == tag.id }
                            FilterChip(
                                selected = on,
                                enabled = on || picked.size < 3,
                                onClick = { if (on) picked.removeAll { it.id == tag.id } else picked.add(tag) },
                                label = { Text(if (tag.enName.isNotBlank()) "${tag.name} · ${tag.enName}" else tag.name) },
                            )
                        }
                    }
                    if (results.isEmpty()) Hint("没有找到相关曲风")
                }
            }
        }
        Spacer(Modifier.size(16.dp))
        GradientButton("确定", { onDone(picked.toList()) }, Modifier.fillMaxWidth())
    }
}

/** 每行一条的文本列表编辑（如副标题）。 */
@Composable
fun LinesEditorSheet(title: String, hint: String, values: List<String>, onDone: (List<String>) -> Unit, onDismiss: () -> Unit) {
    var text by remember { mutableStateOf(values.joinToString("\n")) }
    Sheet(title, onDismiss) {
        AppTextField(text, { text = it }, title, placeholder = hint, singleLine = false, minLines = 4)
        Spacer(Modifier.size(16.dp))
        GradientButton(
            "确定",
            { onDone(text.split("\n").map { it.trim() }.filter { it.isNotEmpty() }) },
            Modifier.fillMaxWidth(),
        )
    }
}

/** 单选列表。 */
@Composable
fun <T> ChoiceSheet(title: String, options: List<Pair<T, String>>, selected: T?, onPick: (T) -> Unit, onDismiss: () -> Unit) {
    Sheet(title, onDismiss) {
        LazyColumn(Modifier.heightIn(max = 480.dp)) {
            itemsIndexed(options) { index, (value, label) ->
                ListItem(
                    headlineContent = { Text(label) },
                    trailingContent = { if (value == selected) Icon(Icons.Rounded.Check, null, tint = MaterialTheme.colorScheme.primary) },
                    colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
                    modifier = Modifier.enterAnimation(index).clickableRow { onPick(value) },
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DatePickerSheet(initial: Long?, onPick: (Long) -> Unit, onDismiss: () -> Unit) {
    val state = rememberDatePickerState(initialSelectedDateMillis = initial ?: System.currentTimeMillis())
    DatePickerDialog(
        onDismissRequest = onDismiss,
        confirmButton = {
            TextButton(onClick = { state.selectedDateMillis?.let(onPick); onDismiss() }) { Text("确定") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    ) {
        DatePicker(state, showModeToggle = true)
    }
}
