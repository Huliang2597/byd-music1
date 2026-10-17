package com.auramusic.wiki.data

import java.io.IOException
import java.net.URI
import java.net.URL
import java.net.URLDecoder
import java.net.URLEncoder
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.Request
import org.json.JSONObject

/** 歌曲百科公开查询（无需登录）。 */
object PublicWiki {
    private const val BASE = "https://ne.cdgz.top/api/contribution?id="
    const val HOME = "https://ne.cdgz.top/"
    private const val UA = "WikiUploader/1.2.1 (Android; PublicWiki)"
    private val ID = Regex("[1-9][0-9]{0,19}")

    fun shortLink(input: String?): String? {
        var text = input.orEmpty()
        val pattern = Regex("(?i)(?<![a-z0-9.\\-])(?:https?://)?(?:www\\.)?163cn\\.tv/[a-z0-9_\\-]+(?![a-z0-9_\\-])")
        repeat(3) {
            pattern.find(text)?.let { match ->
                var link = match.value
                if (!link.regionMatches(0, "http", 0, 4, ignoreCase = true)) link = "https://$link"
                return link.replaceFirst(Regex("(?i)^http://"), "https://")
            }
            val decoded = runCatching { URLDecoder.decode(text, "UTF-8") }.getOrNull() ?: return null
            if (decoded == text) return null
            text = decoded
        }
        return null
    }

    fun normalizeId(input: String?): String? {
        var text = input?.trim().orEmpty()
        if (text.matches(ID)) return text
        val pattern = Regex("(?:[?&#]id=|songId=)([1-9][0-9]{0,19})(?![0-9])")
        repeat(3) {
            pattern.find(text)?.let { return it.groupValues[1] }
            val decoded = runCatching { URLDecoder.decode(text, "UTF-8") }.getOrNull() ?: return null
            if (decoded == text) return null
            text = decoded
        }
        return null
    }

    /** 解析歌曲 ID：直接输入、歌曲链接或 163cn.tv 短链接。 */
    suspend fun resolveId(input: String): String = withContext(Dispatchers.IO) {
        if (input.length > 8192) throw IOException("分享内容过长，请只粘贴歌曲链接")
        val short = shortLink(input)
        if (short == null) {
            return@withContext normalizeId(input) ?: throw IOException("请输入歌曲 ID、网易云歌曲链接或 163cn.tv 短链接")
        }
        var url = URL(short)
        repeat(7) {
            requireShareHost(url)
            songIdAt(url)?.let { return@withContext it }
            if (url.path.matches(Regex("/?(?:m/)?(?:artist|playlist|album)(?:/.*)?"))) {
                throw IOException("短链接指向歌单、专辑或艺人，请复制歌曲链接")
            }
            val request = Request.Builder().url(url)
                .header("User-Agent", UA)
                .header("Accept", "text/html,application/json")
                .build()
            Http.strict.newCall(request).await().use { response ->
                val code = response.code
                if (code in setOf(301, 302, 303, 307, 308)) {
                    val location = response.header("Location")
                    if (location == null || location.length > 8192) throw IOException("短链接缺少有效的跳转地址")
                    val next = URL(url, location)
                    url = if (next.protocol.equals("http", true)) URL("https" + next.toString().substring(4)) else next
                    requireShareHost(url)
                    return@use
                }
                if (code !in 200..299) throw IOException("短链接无法打开（HTTP $code）")
                val html = String(response.readBounded(512 * 1024), Charsets.UTF_8)
                    .replace("&amp;", "&").replace("&#38;", "&").replace("\\/", "/")
                for (match in Regex("https://(?:y\\.)?music\\.163\\.com/[^\\s\"'<>]+", RegexOption.IGNORE_CASE).findAll(html)) {
                    val candidate = URL(match.value)
                    requireShareHost(candidate)
                    songIdAt(candidate)?.let { return@withContext it }
                }
                throw IOException("短链接未指向歌曲，可能已失效或是歌单/艺人链接")
            }
        }
        throw IOException("短链接跳转次数过多，请复制完整歌曲链接")
    }

    private fun requireShareHost(url: URL) {
        val host = url.host.lowercase(Locale.ROOT)
        val ok = url.protocol.equals("https", true) && url.userInfo == null &&
            (url.port == -1 || url.port == 443) &&
            host in setOf("163cn.tv", "www.163cn.tv", "music.163.com", "y.music.163.com")
        if (!ok) throw IOException("短链接跳转到了不支持的地址")
    }

    private fun songIdAt(url: URL): String? {
        if (!url.host.equals("music.163.com", true) && !url.host.equals("y.music.163.com", true)) return null
        val ref = url.ref
        return if (url.path == "/song" || url.path == "/m/song" || (ref != null && ref.matches(Regex("/?song\\?.*")))) {
            normalizeId(url.toString())
        } else {
            null
        }
    }

    suspend fun fetch(id: String): JSONObject = withContext(Dispatchers.IO) {
        if (!id.matches(ID)) throw IOException("请输入正确的歌曲 ID 或网易云歌曲链接")
        val request = Request.Builder().url(BASE + URLEncoder.encode(id, "UTF-8"))
            .header("Accept", "application/json")
            .header("User-Agent", UA)
            .build()
        Http.strict.newCall(request).await().use { response ->
            val code = response.code
            val json = runCatching { JSONObject(String(response.readBounded(2 shl 20), Charsets.UTF_8)) }
                .getOrElse { throw IOException("服务暂时不可用（HTTP $code），请稍后重试") }
            if (code !in 200..299 || !json.optBoolean("ok", false)) {
                throw IOException(json.optString("message", "查询失败，请稍后重试") + "（HTTP $code）")
            }
            if (json.optJSONObject("data") == null) throw IOException("返回数据不完整，请重试")
            json
        }
    }

    /** 网易云图片缩略图地址，只接受 *.music.126.net。 */
    fun thumbnail(raw: String?, size: Int): String? {
        var url = raw?.trim() ?: return null
        if (url.startsWith("//")) url = "https:$url"
        return runCatching {
            val uri = URI(url)
            val host = uri.host?.lowercase(Locale.ROOT) ?: return null
            val scheme = uri.scheme ?: return null
            if (uri.userInfo != null || (uri.port != -1 && uri.port != 443)) return null
            if (!host.endsWith(".music.126.net") || !(scheme.equals("https", true) || scheme.equals("http", true))) return null
            val edge = size.coerceIn(32, 512)
            val query = uri.rawQuery?.split("&")
                ?.filter { it.isNotEmpty() && !it.lowercase(Locale.ROOT).startsWith("param=") }
                ?.joinToString("") { "$it&" }
                .orEmpty()
            "https://$host${uri.rawPath}?${query}param=${edge}y$edge"
        }.getOrNull()
    }
}
