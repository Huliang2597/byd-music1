package com.auramusic.wiki.data

import java.io.IOException
import java.net.URL
import java.net.URLDecoder
import java.net.URLEncoder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

/** 艺人资料读取与修改（网页版 weapi）。 */
class ArtistWiki(credential: String) {
    private val cookies: Map<String, String> = NeteaseAuth.parseCookies(credential)

    class ApiException(message: String) : IOException(message)

    private suspend fun call(path: String, payload: JSONObject): JSONObject = require(weapi(path, payload))

    suspend fun search(keyword: String): JSONArray {
        val text = keyword.trim()
        if (text.isEmpty() || text.length > 200) throw IOException("请输入艺人名或艺人 ID")
        val data = call(SEARCH, JSONObject().put("keyword", text).put("limit", 40)).optJSONObject("data")
        return data?.optJSONArray("list") ?: throw IOException("艺人搜索数据不完整，请重试")
    }

    suspend fun get(id: String): JSONObject {
        val artistId = requireId(id)
        val data = call(GET, JSONObject().put("artistId", artistId)).optJSONObject("data")
        if (data == null || data.optString("artistName", "").isEmpty()) throw IOException("未找到艺人资料，请核对 ID")
        if (data.has("artistId") && artistId != data.optString("artistId")) throw IOException("返回的艺人 ID 不一致，请重新查询")
        return data
    }

    suspend fun permissions(id: String): JSONObject {
        val artistId = requireId(id)
        val privilege = call(PRIVILEGE, JSONObject().put("bizType", 1).put("bizId", artistId))
        if (privilege.optInt("code") != 200) throw IOException("当前账号暂不能修改该艺人资料（${privilege.optInt("code")}）")
        val fields = call(FIELDS, JSONObject().put("resType", 1).put("resId", artistId)).optJSONArray("data")
            ?: throw IOException("无法读取字段修改权限，请刷新重试")
        val result = JSONObject()
        for (item in fields.objects()) {
            val fixType = item.optInt("fixType", -1)
            if (fixType in 1..KEYS.size) result.put(KEYS[fixType - 1], item.optBoolean("isEditable", false))
        }
        return result
    }

    suspend fun submit(change: JSONObject): JSONObject {
        requireId(change.optString("artistId"))
        if (change.optString("source", "").trim().isEmpty()) throw IOException("请填写资料来源")
        if (change.length() <= 3) throw IOException("没有需要提交的修改")
        return call(UPDATE, JSONObject().put("artistChangeVo", change))
    }

    suspend fun uploadImage(bytes: ByteArray): String {
        if (bytes.size < 4 || bytes.size > 20 * 1024 * 1024) throw IOException("图片过大或为空")
        val csrf = cookies["__csrf"]
        var query = "filename=artist.jpg&ext=jpg&type=image&bucket=yyimgs&local=false&nos_product=0"
        if (csrf != null) query += "&csrf_token=" + URLEncoder.encode(csrf, "UTF-8")
        val alloc = require(exchange("https://music.163.com/api/nos/token/alloc?$query", ByteArray(0), "application/x-www-form-urlencoded", null))
        val data = alloc.optJSONObject("data") ?: alloc.optJSONObject("result") ?: throw IOException("无法取得图片上传凭据")
        val bucket = data.optString("bucket")
        val objectKey = data.optString("objectKey")
        val token = data.optString("token")
        if (bucket != "yyimgs" || !objectKey.matches(Regex("[A-Za-z0-9_./=-]+")) || objectKey.contains("..") ||
            token.isEmpty() || token.contains('\r') || token.contains('\n')
        ) {
            throw IOException("图片上传凭据无效")
        }
        var offset = 0
        var context = ""
        while (offset < bytes.size) {
            val end = minOf(bytes.size, offset + 256 * 1024)
            var url = "https://music.163.com/web/proxy/nosupload?offset=$offset&complete=${end == bytes.size}" +
                "&version=1.0&objectkey=" + URLEncoder.encode("$bucket/$objectKey", "UTF-8")
            if (context.isNotEmpty()) url += "&context=" + URLEncoder.encode(context, "UTF-8")
            val res = exchange(url, bytes.copyOfRange(offset, end), "image/jpeg", token)
            if (res.has("code") && !accepted(res.optInt("code"))) require(res)
            if (res.optInt("offset", -1) != end) throw IOException("图片上传未完成，请重试")
            context = res.optString("context", "")
            offset = end
        }
        return "$bucket/$objectKey"
    }

    private suspend fun weapi(path: String, payload: JSONObject): JSONObject {
        val csrf = cookies["__csrf"] ?: ""
        val wire = JSONObject()
        for (key in payload.keys()) {
            val value = payload.get(key)
            wire.put(key, if (value is JSONObject || value is JSONArray) value.toString() else value)
        }
        wire.put("csrf_token", csrf)
        var url = "https://music.163.com/weapi/" + path.substring(5)
        if (csrf.isNotEmpty()) url += "?csrf_token=" + URLEncoder.encode(csrf, "UTF-8")
        return exchange(url, NeteaseCrypto.weapi(wire).encoded().toByteArray(), "application/x-www-form-urlencoded; charset=UTF-8", null)
    }

    private suspend fun exchange(url: String, body: ByteArray, contentType: String, nosToken: String?): JSONObject =
        withContext(Dispatchers.IO) {
            val request = Request.Builder().url(url)
                .post(body.toRequestBody(contentType.toMediaType()))
                .header("Accept", "application/json")
                .header("Origin", "https://music.163.com")
                .header("Referer", "https://music.163.com/wiki/artist")
                .header("User-Agent", Http.APP_UA)
                .apply {
                    if (cookies.isNotEmpty()) header("Cookie", NeteaseAuth.cookieHeader(cookies))
                    if (nosToken != null) header("x-nos-token", nosToken)
                }
                .build()
            Http.strict.newCall(request).await().use { response ->
                val text = String(response.readBounded(2 shl 20), Charsets.UTF_8)
                val code = response.code
                if (code in 300..399) throw IOException("网易云要求重新登录，请在我的页面完成登录")
                if (code !in 200..299) throw IOException("网易云请求失败（HTTP $code），请稍后重试")
                runCatching { JSONObject(text) }.getOrElse { throw IOException("网易云返回的数据格式异常，请稍后重试") }
            }
        }

    companion object {
        private const val FIELDS = "/api/rep/ugc/user/res/privilege"
        private const val GET = "/api/rep/ugc/artist/get"
        private const val PRIVILEGE = "/api/rep/ugc/user/privilege"
        private const val SEARCH = "/api/rep/ugc/artist/search"
        private const val UPDATE = "/api/rep/ugc/artist/update"

        val KEYS = arrayOf("artistName", "alias", "img", "area", "type", "desc", "production", "transName")
        private val LABELS = arrayOf("艺人名", "别名", "艺人图片", "地区", "类型", "艺人简介", "详细介绍", "翻译名")
        val AREAS = intArrayOf(0, 1, 6, 96, 8, 16, 1073741824, 7)
        val AREA_NAMES = arrayOf("未知", "大陆", "港台", "欧美", "日本", "韩国", "其他", "华语")
        val TYPES = intArrayOf(0, 1, 2, 3)
        val TYPE_NAMES = arrayOf("未知", "男", "女", "乐队/组合")
        val IMAGE_KEYS = arrayOf("artistRawCover", "artistHeadRawCover", "artistMainPageCover", "artistHeadCover")

        private val ID = Regex("[1-9][0-9]{0,19}")

        fun accepted(code: Int) = code in NeteaseSession.ACCEPTED

        fun require(res: JSONObject?): JSONObject {
            if (res == null) throw IOException("网易云未返回艺人资料")
            val code = res.optInt("code", 0)
            if (code == 301) throw ApiException("请先在我的页面登录网易云，再使用艺人资料修改")
            if (!accepted(code)) {
                throw ApiException("网易云：" + res.optString("message", res.optString("msg", "请求失败")) + "（$code）")
            }
            return res
        }

        fun pendingImages(): JSONObject = JSONObject().apply { IMAGE_KEYS.forEach { put(it, "yyimgs/pending") } }

        /** 对比原始资料与编辑后的值，生成提交内容。 */
        fun changes(
            id: String,
            original: JSONObject,
            edited: JSONObject,
            permissions: JSONObject,
            images: JSONObject?,
            source: String?,
            notes: String?,
        ): JSONObject {
            val result = JSONObject().put("artistId", requireId(id))
            for (key in KEYS) {
                if (key == "img" || !edited.has(key)) continue
                var before = text(original, key)
                var after = text(edited, key)
                if (key == "alias") {
                    before = aliases(before)
                    after = aliases(after)
                }
                if ((key == "area" || key == "type") && before.isEmpty()) before = "0"
                if (before == after) continue
                if (!permissions.optBoolean(key, false)) throw IOException(label(key) + "暂不允许修改，请重新读取资料")
                if (key == "artistName" && after.isBlank()) throw IOException("艺人名不能为空")
                if (key == "desc" && after.length > 2048) throw IOException("艺人简介不能超过 2048 字")
                if (key == "area" || key == "type") {
                    val value = after.toIntOrNull() ?: throw IOException(label(key) + "无效")
                    val allowed = if (key == "area") AREAS else TYPES
                    if (value !in allowed) throw IOException(label(key) + "无效")
                    result.put(key, value)
                } else {
                    result.put(key, after)
                }
            }
            if (images != null) {
                if (!permissions.optBoolean("img", false)) throw IOException("当前艺人图片不允许修改")
                for (key in IMAGE_KEYS) {
                    val value = images.optString(key, "")
                    if (!value.matches(Regex("yyimgs/[A-Za-z0-9_./=-]+")) || value.contains("..")) {
                        throw IOException("艺人图片上传未完成")
                    }
                    result.put(key, value)
                }
            }
            if (result.length() == 1) throw IOException("没有需要提交的修改")
            if (source.isNullOrBlank()) throw IOException("请填写资料来源，例如艺人官网或官方资料链接")
            return result.put("source", source.trim()).put("notes", notes?.trim().orEmpty())
        }

        fun checkConflicts(original: JSONObject, latest: JSONObject, change: JSONObject) {
            for (key in KEYS) {
                if (!change.has(key)) continue
                var before = text(original, key)
                var now = text(latest, key)
                if (key == "alias") {
                    before = aliases(before)
                    now = aliases(now)
                }
                if (before != now) throw IOException(label(key) + "已在网易云发生变化，请重新读取后核对修改")
            }
            if (change.has("artistRawCover")) {
                for (key in arrayOf("headPicUrl", "avatarPicUrl")) {
                    if (text(original, key) != text(latest, key)) throw IOException("艺人图片已变化，请重新读取后再修改")
                }
            }
        }

        fun label(key: String): String = KEYS.indexOf(key).let { if (it >= 0) LABELS[it] else key }

        fun text(json: JSONObject?, key: String): String {
            if (json == null || json.isNull(key)) return ""
            val value = json.opt(key)
            if (value is JSONArray && key == "alias") {
                return (0 until value.length()).joinToString(";") { value.optString(it, "") }
            }
            return json.optString(key, "").replace("\r\n", "\n")
        }

        fun aliases(text: String): String =
            text.split(Regex("[;；\r\n]+")).map { it.trim() }.filter { it.isNotEmpty() }.joinToString(";")

        fun requireId(id: String?): String {
            if (id == null || !id.matches(ID)) throw IOException("艺人 ID 无效")
            return id
        }

        fun normalizeId(input: String?): String? {
            var text = input?.trim().orEmpty()
            if (text.matches(ID)) return text
            repeat(3) {
                for (match in Regex("https?://(?:music|y\\.music)\\.163\\.com/[^\\s<>\"]+", RegexOption.IGNORE_CASE).findAll(text)) {
                    val url = runCatching { URL(match.value) }.getOrNull() ?: continue
                    if (url.userInfo != null || (url.port != -1 && url.port != 443)) continue
                    var path = url.path
                    val ref = url.ref
                    if (ref != null && (path == "/" || path.isEmpty())) path = ref
                    if (path.matches(Regex("/?(?:m/|wiki/)?artist(?:[?/].*)?"))) {
                        Regex("[?&](?:artistId|id)=([1-9][0-9]{0,19})(?![0-9])").find(url.toString())?.let {
                            return it.groupValues[1]
                        }
                    }
                }
                val decoded = runCatching { URLDecoder.decode(text, "UTF-8") }.getOrNull() ?: return null
                if (decoded == text) return null
                text = decoded
            }
            return null
        }
    }
}
