package com.auramusic.wiki.data

import org.json.JSONObject

data class Account(val userId: Long, val nickname: String, val avatarUrl: String?)

enum class Channel(val label: String) {
    AUTO("自动"),
    EAPI("App 通道 (eapi)"),
    WEAPI("网页通道 (weapi)"),
}

enum class QrState { WAITING, SCANNED, CONFIRMED, EXPIRED, VERIFY, ERROR }

data class QrStatus(val state: QrState, val nickname: String? = null, val message: String? = null)

/** 歌曲或专辑里的艺人；id 为空表示新艺人，交给审核人员建档。 */
data class WikiArtist(val id: Long?, val name: String, val avatarUrl: String? = null) {
    fun toJson(): JSONObject = JSONObject()
        .put("artistId", id ?: JSONObject.NULL)
        .put("artistName", name)
}

data class WikiTag(val id: String, val name: String, val enName: String)

data class ArtistDetail(val id: Long, val name: String, val avatarUrl: String?)

data class SongDetail(
    val id: Long,
    val name: String,
    val subTitle: String,
    val transName: String,
    val company: String,
    val publishTime: Long,
    val language: String,
    val originalCover: Int,
    val artists: List<WikiArtist>,
    val lyricArtists: List<WikiArtist>,
    val composeArtists: List<WikiArtist>,
    val arrangeArtists: List<WikiArtist>,
    val albumName: String,
    val lyric: String,
    val transLyric: String,
    val durationMs: Long,
    val playUrl: String?,
    val lyricLocked: Boolean,
    val transLyricLocked: Boolean,
)

data class SongHit(val id: Long, val name: String, val subtitle: String)

data class LyricCheck(val ok: Boolean, val message: String, val failures: List<String>)

data class Contribution(
    val name: String,
    val bizId: Long,
    val createTime: Long,
    val status: Int,
    val artists: String,
    val approved: List<String>,
    val rejected: List<String>,
)

data class Page<T>(val items: List<T>, val total: Int)

data class TaskGroup(
    val missionId: Long,
    val name: String,
    val picUrl: String?,
    val url: String?,
    val resCount: Int,
    val userCount: Int,
)

data class TaskInfo(val name: String, val desc: String, val resCount: Int, val userCount: Int)

data class TaskItem(
    val resId: Long,
    val resName: String,
    val artistName: String,
    val missionId: Long,
    val resType: Int,
    val reward: String,
    val heat: String,
    val status: Int?,
    val deadline: Long?,
    val subAction: String,
)

data class Recommend(val group: TaskGroup, val type: Int, val items: List<TaskItem>)

data class Devote(val ugcCount: Int, val cloudShell: Int)

/** 已上传到网易云 NOS 的文件。 */
data class NosFile(
    val fileName: String,
    val fileSize: Long,
    val mime: String,
    val bucket: String,
    val objectKey: String,
    val docId: String,
    val resourceId: String,
    val md5: String,
) {
    val nosKey: String get() = "$bucket/$objectKey"

    fun toJson(): JSONObject = JSONObject()
        .put("code", 200)
        .put("fileName", fileName)
        .put("fileSize", fileSize)
        .put("type", mime)
        .put("bucket", bucket)
        .put("docId", docId)
        .put("objectKey", objectKey)
        .put("resourceId", resourceId)
        .put("md5", md5)
        .put("jdUrl", "$bucket.nos-jd.163yun.com/$objectKey")
        .put("hzUrl", "nos.netease.com/$bucket/$objectKey")
        .put("nosKey", nosKey)
}

enum class UploadKind { AUDIO, IMAGE }

class WikiException(message: String) : Exception(message)
