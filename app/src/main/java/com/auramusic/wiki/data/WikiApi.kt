package com.auramusic.wiki.data

import org.json.JSONArray
import org.json.JSONObject

/** 网易云曲库共建（UGC）接口。 */
class WikiApi(private val session: NeteaseSession) {

    suspend fun song(songId: Long): SongDetail {
        val data = session.call("/api/rep/ugc/song/get", mapOf("songId" to songId)).optJSONObject("data")
            ?: throw WikiException("找不到这首歌")
        return SongDetail(
            id = data.optLong("songId", songId),
            name = data.str("songName"),
            subTitle = data.str("songSubTitle"),
            transName = data.str("transName"),
            company = data.str("company"),
            publishTime = data.optLong("publishTime"),
            language = data.str("language"),
            originalCover = data.optInt("originalCover"),
            artists = artists("artistRepVos", data),
            lyricArtists = artists("lyricArtists", data),
            composeArtists = artists("composeArtists", data),
            arrangeArtists = artists("arrangeArtists", data),
            albumName = data.optJSONObject("albumRepVo")?.str("albumName").orEmpty(),
            lyric = data.str("lyricContent"),
            transLyric = data.str("transLyricContent"),
            durationMs = data.optLong("duration"),
            playUrl = normalizeUrl(data.str("playUrl")),
            lyricLocked = data.optInt("lyricLock") == 1,
            transLyricLocked = data.optInt("transLyricLock") == 1,
        )
    }

    /** 字段修改权限：fixType → 是否可编辑。 */
    suspend fun privileges(resType: Int, resId: Long): Map<Int, Boolean> {
        val res = session.call("/api/rep/ugc/user/res/privilege", mapOf("resType" to resType, "resId" to resId))
        return res.optJSONArray("data").objects().associate {
            it.optInt("fixType") to it.optBoolean("isEditable", it.optInt("isEditable") == 1)
        }
    }

    suspend fun updateSong(change: JSONObject) {
        session.call("/api/rep/ugc/song/update", mapOf("songChangeVo" to change))
    }

    suspend fun checkLyric(type: String, content: String, durationMs: Long, refer: String? = null): LyricCheck {
        val params = linkedMapOf<String, Any?>("type" to type, "content" to content, "duration" to durationMs)
        if (type == "trans") {
            params["referType"] = "lrc"
            params["referContent"] = refer ?: content
        }
        val data = session.call("/api/music/wiki/ugc/lyric/check", params).optJSONObject("data")
            ?: return LyricCheck(true, "", emptyList())
        val lines = content.split("\n")
        val failures = data.optJSONArray("failColumns").objects().map { column ->
            val index = column.optInt("index")
            val stamp = lines.getOrNull(index)?.let { Regex("\\[.*?]").find(it)?.value }.orEmpty()
            val messages = column.optJSONArray("messages")
            val text = if (messages == null) "" else (0 until messages.length()).joinToString("/") { messages.optString(it) }
            "第${index + 1}行 $stamp：$text"
        }
        return LyricCheck(data.optBoolean("result", true), data.str("message"), failures)
    }

    suspend fun searchSongs(keyword: String): List<SongHit> {
        val res = session.call(
            "/api/cloudsearch/pc",
            mapOf("s" to keyword, "type" to 1, "limit" to 30, "offset" to 0),
        )
        return res.optJSONObject("result")?.optJSONArray("songs").objects().map { song ->
            val artists = (song.optJSONArray("ar") ?: song.optJSONArray("artists")).objects()
                .joinToString(" / ") { it.str("name") }
            val album = (song.optJSONObject("al") ?: song.optJSONObject("album"))?.str("name").orEmpty()
            SongHit(song.optLong("id"), song.str("name"), listOf(artists, album).filter { it.isNotBlank() }.joinToString(" · "))
        }
    }

    suspend fun searchArtists(keyword: String): List<WikiArtist> {
        val res = session.call("/api/rep/ugc/artist/search", mapOf("keyword" to keyword, "limit" to 40))
        return res.optJSONObject("data")?.optJSONArray("list").objects().map {
            WikiArtist(it.optLong("artistId"), it.str("artistName"), normalizeUrl(it.str("artistAvatarPicUrl")))
        }
    }

    suspend fun artist(artistId: Long): ArtistDetail {
        val data = session.call("/api/rep/ugc/artist/get", mapOf("artistId" to artistId)).optJSONObject("data")
            ?: throw WikiException("找不到这个艺人")
        return ArtistDetail(data.optLong("artistId", artistId), data.str("artistName"), normalizeUrl(data.str("avatarPicUrl")))
    }

    suspend fun tags(keyword: String): List<WikiTag> {
        val res = session.call(
            "/api/rep/ugc/tag/list",
            mapOf("tagName" to keyword, "resType" to 2, "categoryName" to "STYLE_TAG"),
        )
        return res.optJSONArray("data").objects().map { WikiTag(it.str("id"), it.str("name"), it.str("enName")) }
    }

    suspend fun addAlbum(artistId: Long, album: JSONObject) {
        session.call("/api/rep/ugc/add/artist/album", mapOf("albumVo" to album, "artistId" to artistId))
    }

    suspend fun devote(): Devote {
        val data = session.call("/api/rep/ugc/user/devote").optJSONObject("data") ?: JSONObject()
        return Devote(data.optInt("ugcCount"), data.optInt("cloudShell"))
    }

    suspend fun contributions(type: Int, auditStatus: Int?, offset: Int, limit: Int): Page<Contribution> {
        val params = linkedMapOf<String, Any?>(
            "type" to type, "limit" to limit, "offset" to offset, "order" to "desc", "sortBy" to "createTime",
        )
        if (auditStatus != null) params["auditStatus"] = auditStatus
        val data = session.call("/api/rep/ugc/detail", params).optJSONObject("data") ?: JSONObject()
        val items = data.optJSONArray("wikiDetailResultVoList").objects().map {
            val artists = (it.optJSONArray("artists") ?: it.optJSONArray("artistSimpleVos")).objects()
                .joinToString(" / ") { a -> a.str("artistName").ifBlank { a.str("name") } }
            Contribution(
                name = it.str("name"),
                bizId = it.optLong("bizId"),
                createTime = it.optLong("createTime"),
                status = it.optInt("status"),
                artists = artists,
                approved = it.optJSONArray("approveNames").strings(),
                rejected = it.optJSONArray("rejectNames").strings(),
            )
        }
        return Page(items, data.optInt("total"))
    }

    suspend fun recommendTasks(): List<Recommend> {
        val res = session.call("/api/rep/ugc/task/recommend/list")
        val list = res.optJSONArray("data") ?: res.optJSONObject("data")?.optJSONArray("records")
        return list.objects().map { entry ->
            val vo = entry.optJSONObject("taskVo") ?: JSONObject()
            val type = vo.optInt("resType")
            Recommend(group(vo), type, entry.optJSONArray("taskDetailVos").objects().map { item(it, type) })
        }
    }

    suspend fun taskGroups(type: Int): List<TaskGroup> {
        val res = session.call("/api/rep/ugc/task/list/resource", mapOf("type" to type))
        return res.optJSONObject("data")?.optJSONArray("records").objects().map { group(it) }
    }

    suspend fun taskInfo(missionId: Long): TaskInfo {
        val data = session.call("/api/rep/ugc/task/get", mapOf("missionId" to missionId)).optJSONObject("data") ?: JSONObject()
        return TaskInfo(data.str("taskName"), data.str("taskDesc"), data.optInt("resCont"), data.optInt("userCont"))
    }

    suspend fun taskItems(
        missionId: Long,
        type: Int,
        query: String,
        language: String?,
        offset: Int,
        limit: Int,
    ): Page<TaskItem> {
        val params = linkedMapOf<String, Any?>(
            "missionId" to missionId, "queryText" to query, "limit" to limit, "offset" to offset, "type" to type,
        )
        if (!language.isNullOrBlank()) params["language"] = language
        val data = session.call("/api/rep/ugc/task/detail", params).optJSONObject("data") ?: JSONObject()
        return Page(
            data.optJSONArray("records").objects().map { item(it, type) },
            data.optJSONObject("page")?.optInt("total") ?: 0,
        )
    }

    suspend fun myTasks(type: Int, status: Int?, offset: Int, limit: Int): Page<TaskItem> {
        val params = linkedMapOf<String, Any?>("limit" to limit, "offset" to offset, "type" to type)
        if (status != null) params["status"] = status
        val data = session.call("/api/rep/ugc/task/user/receive/list", params).optJSONObject("data") ?: JSONObject()
        return Page(
            data.optJSONArray("records").objects().map { item(it, type) },
            data.optJSONObject("page")?.optInt("total") ?: 0,
        )
    }

    suspend fun claimTask(item: TaskItem) {
        session.call("/api/rep/ugc/task/receive", mapOf("resourceId" to item.resId, "missionId" to item.missionId))
    }

    private fun group(json: JSONObject) = TaskGroup(
        missionId = json.optLong("missionId"),
        name = json.str("taskName"),
        picUrl = normalizeUrl(json.str("taskPic")),
        url = json.strOrNull("taskUrl"),
        resCount = json.optInt("resCont"),
        userCount = json.optInt("userCont"),
    )

    private fun item(json: JSONObject, type: Int): TaskItem {
        val start = json.optLong("startTime").takeIf { it > 0 }
        return TaskItem(
            resId = json.optLong("resId"),
            resName = json.str("resName"),
            artistName = json.str("artistName"),
            missionId = json.optLong("missionId"),
            resType = json.optInt("resType", type),
            reward = json.str("cloudShell"),
            heat = json.str("score"),
            status = if (json.has("status")) json.optInt("status") else null,
            deadline = start?.let { it + json.optLong("duration") * 1000 },
            subAction = json.str("subAction"),
        )
    }

    private fun artists(key: String, json: JSONObject): List<WikiArtist> =
        json.optJSONArray(key).objects().map {
            WikiArtist(it.optLong("artistId").takeIf { id -> id > 0 }, it.str("artistName"))
        }

    companion object {
        val ALBUM_TYPES = listOf("专辑", "EP", "Single", "精选集", "合集", "DEMO")
        val LANGUAGES = listOf(
            "国语", "粤语", "闽南语", "英语", "日语", "韩语", "纯音乐", "其他", "未知", "德语", "法语", "西班牙语",
            "葡萄牙语", "意大利语", "俄语", "泰语", "越南语", "印尼语", "马来语", "菲律宾语", "印地语", "阿拉伯语",
            "土耳其语", "荷兰语", "瑞典语", "芬兰语", "波兰语", "乌克兰语", "拉丁语", "藏语", "维吾尔语", "蒙古语",
            "客家话", "上海话", "四川话", "东北话",
        )
        val EXCLUSIVE_LANGUAGES = setOf("未知", "其他", "纯音乐")
        val AUDIT_STATUS = linkedMapOf(0 to "待审核", 1 to "审核中", 4 to "部分通过", 5 to "审核通过", -5 to "未采纳")
        val TASK_STATUS = linkedMapOf(-1 to "已过期", 0 to "进行中", 20 to "审核中", 30 to "未通过", 100 to "已完成")
        val AUDIO_ERRORS = listOf(1 to "音频与歌曲不符", 2 to "音质太低", 3 to "音频有杂音或卡顿", 4 to "其他")
        val TASK_LINK_TYPES = mapOf(1 to "artist", 2 to "album", 3 to "song", 4 to "mv")

        fun artistsJson(list: List<WikiArtist>): JSONArray = JSONArray(list.map { it.toJson() })
    }
}
