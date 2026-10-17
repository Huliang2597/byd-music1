package com.auramusic.wiki.data

import java.io.IOException
import java.net.HttpCookie
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

/** 网易云登录：扫码、Cookie 校验。每个实例维护一次登录过程的 Cookie。 */
class NeteaseAuth private constructor() {
    private val cookies = LinkedHashMap<String, String>()
    private val createdAt = System.currentTimeMillis()

    class ExpiredSessionException : IOException("登录凭据无效或已过期，请重新登录（网易云 301）")

    private suspend fun createQr(): String {
        val res = post("/api/login/qrcode/unikey", JSONObject().put("type", 1))
        val data = res.optJSONObject("data")
        val key = res.optString("unikey", data?.optString("unikey") ?: "")
        if (res.optInt("code", 200) != 200 || key.isEmpty()) throw failure("获取二维码失败", res)
        return key
    }

    private suspend fun pollQr(key: String): JSONObject {
        val res = post("/api/login/qrcode/client/login", JSONObject().put("key", key).put("type", 1))
        if (res.optInt("code") == 803) {
            val cookie = if (res.isNull("cookie")) "" else res.optString("cookie", "")
            if (cookie.isNotEmpty()) cookies.putAll(parseCookies(cookie))
            requireCredential(cookies)
            res.put("cookie", cookieHeader(cookies))
        }
        return res
    }

    /** 校验 Cookie，返回 { profile, cookies }。 */
    suspend fun verify(raw: String): JSONObject {
        cookies.clear()
        cookies.putAll(parseCookies(raw))
        var res = post("/api/w/nuser/account/get", JSONObject())
        if (res.optInt("code") == 404 || (res.optInt("code") == 200 && res.optJSONObject("profile") == null)) {
            res = post("/api/nuser/account/get", JSONObject())
        }
        val profile = requireProfile(res)
        requireCredential(cookies)
        return JSONObject().put("profile", profile).put("cookies", JSONObject(cookies as Map<*, *>))
    }

    private suspend fun post(path: String, payload: JSONObject): JSONObject {
        payload.put("csrf_token", cookies["__csrf"] ?: "")
        val body = NeteaseCrypto.weapi(payload).encoded()
            .toRequestBody("application/x-www-form-urlencoded; charset=UTF-8".toMediaType())
        val request = Request.Builder()
            .url("https://music.163.com/weapi/" + path.removePrefix("/api/"))
            .post(body)
            .header("Accept", "application/json")
            .header("User-Agent", Http.APP_UA)
            .header("Origin", "https://music.163.com")
            .header("Referer", "https://music.163.com/st/webplayer")
            .apply { if (cookies.isNotEmpty()) header("Cookie", cookieHeader(cookies)) }
            .build()
        Http.strict.newCall(request).await().use { response ->
            for (header in response.headers("Set-Cookie")) {
                val parsed = runCatching { HttpCookie.parse(header) }.getOrNull() ?: continue
                for (cookie in parsed) {
                    val domain = cookie.domain
                    if (domain != null && !domain.equals("music.163.com", true) && !domain.equals(".music.163.com", true)) continue
                    if (!cookie.hasExpired() && cookie.value.isNotEmpty()) {
                        putCookie(cookies, cookie.name, cookie.value)
                    } else {
                        cookies.remove(cookie.name)
                    }
                }
            }
            val text = String(response.readBounded(1 shl 20), Charsets.UTF_8)
            val code = response.code
            if (code == 404) return JSONObject().put("code", 404)
            if (code !in 200..299) throw IOException("网易云登录请求失败（HTTP $code），请稍后重试或使用官网登录")
            return runCatching { JSONObject(text) }
                .getOrElse { throw IOException("网易云未返回有效登录数据，请使用官网登录") }
        }
    }

    companion object {
        private const val QR_TTL = 300_000L
        private val qrSessions = LinkedHashMap<String, NeteaseAuth>()

        fun qrUrl(key: String) = "https://music.163.com/login?codekey=$key"

        suspend fun createQrKey(): String {
            val client = NeteaseAuth()
            val key = client.createQr()
            synchronized(qrSessions) {
                qrSessions.values.removeAll { System.currentTimeMillis() - it.createdAt > QR_TTL }
                while (qrSessions.size >= 4) qrSessions.remove(qrSessions.keys.first())
                qrSessions[key] = client
            }
            return key
        }

        suspend fun checkQr(key: String): JSONObject {
            val client = synchronized(qrSessions) { qrSessions[key] }
            if (client == null || System.currentTimeMillis() - client.createdAt > QR_TTL) {
                return JSONObject().put("code", 800).put("message", "二维码已过期，请刷新")
            }
            val res = client.pollQr(key)
            val code = res.optInt("code")
            if (code == 800 || code == 803) synchronized(qrSessions) { qrSessions.remove(key) }
            return res
        }

        suspend fun authenticateCookie(raw: String): JSONObject = NeteaseAuth().verify(raw)

        fun requireProfile(response: JSONObject): JSONObject {
            var res = response
            val data = res.optJSONObject("data")
            if (data != null && data.has("profile")) res = data
            if (res.optInt("code") == 301) throw ExpiredSessionException()
            val profile = res.optJSONObject("profile")
            if (res.optInt("code") != 200 || profile == null || profile.optLong("userId") <= 0) {
                throw failure("未能验证账号，请在官方页面完成登录或验证后重试", res)
            }
            return profile
        }

        fun parseCookies(raw: String?): LinkedHashMap<String, String> {
            var text = raw?.trim().orEmpty()
            if (text.length > 65536) throw IOException("登录凭据内容过长")
            if (text.startsWith("Cookie:") || text.startsWith("cookie:")) text = text.substring(7).trim()
            if (text.length >= 2 &&
                ((text.startsWith("\"") && text.endsWith("\"")) || (text.startsWith("'") && text.endsWith("'")))
            ) {
                text = text.substring(1, text.length - 1)
            }
            text = text.replaceFirst(Regex("(?i)^cookie:\\s*"), "")
            val map = LinkedHashMap<String, String>()
            if (text.startsWith("{")) {
                try {
                    val json = JSONObject(text)
                    for (key in json.keys()) putCookie(map, key, json.optString(key, ""))
                } catch (e: Exception) {
                    throw IOException("登录凭据 JSON 格式不正确")
                }
            } else {
                for (part in text.split(Regex("[;\\r\\n]+"))) {
                    val item = part.trim().replaceFirst(Regex("(?i)^set-cookie:\\s*"), "")
                    val eq = item.indexOf('=')
                    if (eq > 0) putCookie(map, item.substring(0, eq).trim(), item.substring(eq + 1).trim())
                }
                if (!map.containsKey("MUSIC_U") && text.matches(Regex("[A-Za-z0-9_./%+~=-]{40,8192}"))) {
                    map["MUSIC_U"] = text
                }
            }
            requireCredential(map)
            return map
        }

        private fun authCookie(name: String) = name in setOf(
            "MUSIC_U", "__csrf", "MUSIC_A_T", "MUSIC_R_T", "NMTID", "MUSIC_A", "JSESSIONID-WYYY",
        )

        private val cookieValue = Regex("[^\\x00-\\x20;\\x7f]+")

        private fun putCookie(map: MutableMap<String, String>, name: String, value: String) {
            if (!authCookie(name) || value.length > 8192 || !value.matches(cookieValue)) return
            map[name] = value
        }

        private fun requireCredential(map: Map<String, String>) {
            val token = map["MUSIC_U"]
            if (token == null || token.length < 40) throw IOException("未识别到完整的 MUSIC_U 登录凭据")
        }

        fun cookieHeader(map: Map<String, String>): String = map.entries
            .filter { authCookie(it.key) && it.value.matches(cookieValue) }
            .joinToString("; ") { "${it.key}=${it.value}" }

        fun failure(message: String, response: JSONObject) =
            IOException("$message（网易云 ${response.optInt("code", -1)}）")
    }
}
