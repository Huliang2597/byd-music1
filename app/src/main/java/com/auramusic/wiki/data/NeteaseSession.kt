package com.auramusic.wiki.data

import android.content.Context
import android.content.SharedPreferences
import java.util.Locale
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import okhttp3.FormBody
import okhttp3.Request
import okhttp3.Response
import org.json.JSONArray
import org.json.JSONObject

/** 登录状态、Cookie 与网易云接口通道（eapi / weapi）。 */
class NeteaseSession(context: Context) {
    private val prefs: SharedPreferences =
        context.getSharedPreferences("netease_session", Context.MODE_PRIVATE)

    val deviceId: String = prefs.getString("device_id", null) ?: UUID.randomUUID().toString()
        .replace("-", "").uppercase(Locale.ROOT)
        .also { prefs.edit().putString("device_id", it).apply() }

    private val cookies = LinkedHashMap<String, String>().apply {
        prefs.getString("cookies", null)?.let { raw ->
            runCatching {
                val json = JSONObject(raw)
                for (key in json.keys()) put(key, json.getString(key))
            }
        }
    }

    private val _account = MutableStateFlow(loadAccount())
    val account: StateFlow<Account?> = _account.asStateFlow()

    private val _channel = MutableStateFlow(loadChannel())
    val channel: StateFlow<Channel> = _channel.asStateFlow()

    val hasCredential: Boolean get() = synchronized(cookies) { cookies["MUSIC_U"] != null }

    private fun loadAccount(): Account? {
        val raw = prefs.getString("account", null) ?: return null
        return runCatching {
            val json = JSONObject(raw)
            val avatar = json.optString("avatar").takeUnless { it.isBlank() || it == "null" }
            Account(json.getLong("id"), json.optString("name"), avatar)
        }.getOrNull()
    }

    private fun loadChannel(): Channel =
        runCatching { Channel.valueOf(prefs.getString("channel", null) ?: "AUTO") }.getOrDefault(Channel.AUTO)

    fun setChannel(channel: Channel) {
        prefs.edit().putString("channel", channel.name).apply()
        _channel.value = channel
    }

    /** 原始 Cookie 串，供艺人资料修改使用。 */
    fun credential(): String = synchronized(cookies) {
        runCatching { NeteaseAuth.cookieHeader(NeteaseAuth.parseCookies(JSONObject(cookies as Map<*, *>).toString())) }
            .getOrDefault("")
    }

    fun logout() {
        synchronized(cookies) { cookies.clear() }
        prefs.edit().remove("cookies").remove("account").apply()
        _account.value = null
    }

    /** 保存登录结果 { profile, cookies }。 */
    fun accept(result: JSONObject): Account {
        val profile = result.getJSONObject("profile")
        val account = Account(
            profile.getLong("userId"),
            profile.optString("nickname"),
            profile.optString("avatarUrl").takeUnless { it.isBlank() || it == "null" },
        )
        val jar = result.getJSONObject("cookies")
        val map = LinkedHashMap<String, String>()
        for (key in jar.keys()) map[key] = jar.getString(key)
        val accountJson = JSONObject().put("id", account.userId).put("name", account.nickname)
            .put("avatar", account.avatarUrl)
        prefs.edit().putString("cookies", jar.toString()).putString("account", accountJson.toString()).apply()
        synchronized(cookies) {
            cookies.clear()
            cookies.putAll(map)
        }
        _account.value = account
        return account
    }

    suspend fun loginWithCookie(raw: String): Account = withContext(Dispatchers.IO) {
        accept(NeteaseAuth.authenticateCookie(raw))
    }

    suspend fun createQrKey(): String = withContext(Dispatchers.IO) { NeteaseAuth.createQrKey() }

    suspend fun checkQr(key: String): QrStatus = withContext(Dispatchers.IO) {
        val res = NeteaseAuth.checkQr(key)
        when (res.optInt("code")) {
            800 -> QrStatus(QrState.EXPIRED, message = "二维码已过期，请刷新")
            801 -> QrStatus(QrState.WAITING)
            802 -> QrStatus(QrState.SCANNED, nickname = res.optString("nickname"))
            803 -> {
                accept(NeteaseAuth.authenticateCookie(res.optString("cookie")))
                QrStatus(QrState.CONFIRMED)
            }
            else -> QrStatus(QrState.ERROR, message = NeteaseAuth.failure("扫码登录未完成，请尝试官网登录", res).message)
        }
    }

    /** 启动时静默刷新账号资料；凭据过期则退出登录。 */
    suspend fun refresh(): Account? = withContext(Dispatchers.IO) {
        val token = synchronized(cookies) { cookies["MUSIC_U"] } ?: return@withContext null
        try {
            val header = synchronized(cookies) { NeteaseAuth.cookieHeader(cookies) }
            val result = NeteaseAuth.authenticateCookie(header)
            if (token == synchronized(cookies) { cookies["MUSIC_U"] }) accept(result) else _account.value
        } catch (e: NeteaseAuth.ExpiredSessionException) {
            if (token == synchronized(cookies) { cookies["MUSIC_U"] }) logout()
            null
        } catch (e: Exception) {
            _account.value
        }
    }

    // ---------------- 接口调用 ----------------

    suspend fun call(path: String, params: Map<String, Any?> = emptyMap()): JSONObject = withContext(Dispatchers.IO) {
        val payload = JSONObject()
        for ((key, value) in params) {
            when (value) {
                null -> Unit
                is JSONObject, is JSONArray -> payload.put(key, value.toString())
                is Map<*, *> -> payload.put(key, JSONObject(value).toString())
                is Collection<*> -> payload.put(key, JSONArray(value).toString())
                else -> payload.put(key, value.toString())
            }
        }
        val res = when (_channel.value) {
            Channel.EAPI -> eapi(path, payload)
            Channel.WEAPI -> weapi(path, payload)
            Channel.AUTO -> {
                val first = runCatching { eapi(path, JSONObject(payload.toString())) }
                val code = first.getOrNull()?.optInt("code", 200)
                if (first.isFailure || code == 404 || code == -460 || code == 301) {
                    runCatching { weapi(path, payload) }.getOrElse { first.getOrThrow() }
                } else {
                    first.getOrThrow()
                }
            }
        }
        val code = res.optInt("code", 200)
        if (code == 301) throw WikiException("登录已失效，请重新登录")
        if (code in ACCEPTED) return@withContext res
        val message = res.strOrNull("message") ?: res.strOrNull("msg") ?: "操作失败（$code）"
        throw WikiException(message)
    }

    private suspend fun eapi(path: String, payload: JSONObject): JSONObject {
        val now = System.currentTimeMillis()
        val (csrf, token) = synchronized(cookies) { cookies["__csrf"] to cookies["MUSIC_U"] }
        val header = JSONObject()
            .put("os", "android").put("appver", "8.20.20").put("osver", "14")
            .put("deviceId", deviceId).put("versioncode", "8200")
            .put("buildver", (now / 1000).toString()).put("resolution", "1080x2400")
            .put("requestId", "${now}_" + (now % 1000).toString().padStart(4, '0'))
            .put("channel", "xiaomi").put("__csrf", csrf ?: "")
        if (token != null) header.put("MUSIC_U", token)
        payload.put("header", header.toString())
        val params = NeteaseCrypto.eapi(path, payload.toString())
        val cookie = buildString {
            append("os=android; appver=8.20.20; deviceId=$deviceId; channel=xiaomi")
            if (token != null) append("; MUSIC_U=$token")
            if (csrf != null) append("; __csrf=$csrf")
        }
        val request = Request.Builder()
            .url("https://interface3.music.163.com/e" + path.removePrefix("/"))
            .post(FormBody.Builder().add("params", params).build())
            .header("User-Agent", "NeteaseMusic/8.20.20.240716 (Linux; Android 14)")
            .header("Referer", "https://music.163.com/")
            .header("Cookie", cookie)
            .build()
        return Http.api.newCall(request).await().use { parse(it) }
    }

    private suspend fun weapi(path: String, payload: JSONObject): JSONObject {
        val csrf = synchronized(cookies) { cookies["__csrf"] } ?: ""
        payload.put("csrf_token", csrf)
        val form = NeteaseCrypto.weapi(payload)
        val request = Request.Builder()
            .url("https://music.163.com/weapi/" + path.removePrefix("/api/") + "?csrf_token=" + csrf)
            .post(FormBody.Builder().add("params", form.params).add("encSecKey", form.encSecKey).build())
            .header("User-Agent", Http.CHROME_UA)
            .header("Referer", "https://music.163.com/st/wiki/")
            .header("Origin", "https://music.163.com")
            .header("Cookie", webCookie())
            .build()
        return Http.api.newCall(request).await().use { parse(it) }
    }

    private fun parse(response: Response): JSONObject {
        captureCookies(response)
        if (response.code == 404) return JSONObject().put("code", 404)
        if (response.code !in 200..299) throw WikiException("网易云请求失败（HTTP ${response.code}）")
        val text = response.body?.string().orEmpty().ifBlank { "{}" }
        return JSONObject(text)
    }

    fun captureCookies(response: Response) {
        var changed = false
        for (header in response.headers("Set-Cookie")) {
            val pair = header.substringBefore(';')
            val name = pair.substringBefore('=').trim()
            val value = pair.substringAfter('=', "").trim()
            if (name in TRACKED && value.isNotEmpty()) {
                synchronized(cookies) { cookies[name] = value }
                changed = true
            }
        }
        if (changed) {
            val json = synchronized(cookies) { JSONObject(cookies as Map<*, *>).toString() }
            prefs.edit().putString("cookies", json).apply()
        }
    }

    /** 网页端请求使用的 Cookie 头。 */
    fun webCookie(): String = buildString {
        append("os=pc; appver=2.10.13")
        synchronized(cookies) {
            for ((key, value) in cookies) append("; ").append(key).append('=').append(value)
        }
    }

    companion object {
        private val TRACKED = setOf("MUSIC_U", "__csrf", "MUSIC_A_T", "MUSIC_R_T", "NMTID")
        val ACCEPTED = setOf(200, 206, 310, 320, 330)
    }
}
