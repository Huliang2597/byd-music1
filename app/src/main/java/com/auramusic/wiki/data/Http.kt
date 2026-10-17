package com.auramusic.wiki.data

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine
import okhttp3.Call
import okhttp3.Callback
import okhttp3.OkHttpClient
import okhttp3.Response
import org.json.JSONArray
import org.json.JSONObject

object Http {
    const val CHROME_UA =
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    const val APP_UA = "WikiUploader/1.2.3 (Android)"

    /** 不跟随跳转、超时较短，用于登录、短链解析和公开图片。 */
    val strict: OkHttpClient = OkHttpClient.Builder()
        .followRedirects(false)
        .followSslRedirects(false)
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    /** 接口和上传使用，超时更长。 */
    val api: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(120, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()
}

/** 协程挂起执行请求，协程取消时同时取消网络请求。 */
suspend fun Call.await(): Response = suspendCancellableCoroutine { cont ->
    cont.invokeOnCancellation { runCatching { cancel() } }
    enqueue(object : Callback {
        override fun onFailure(call: Call, e: IOException) {
            if (cont.isActive) cont.resumeWithException(e)
        }

        override fun onResponse(call: Call, response: Response) {
            if (cont.isActive) cont.resumeWith(Result.success(response)) else response.close()
        }
    })
}

fun Response.readBounded(limit: Int): ByteArray {
    val source = body?.byteStream() ?: return ByteArray(0)
    source.use { input ->
        val out = java.io.ByteArrayOutputStream()
        val buffer = ByteArray(8192)
        while (true) {
            val read = input.read(buffer)
            if (read < 0) break
            if (out.size() + read > limit) throw IOException("返回内容过大，请换一首歌曲重试")
            out.write(buffer, 0, read)
        }
        return out.toByteArray()
    }
}

fun JSONObject.str(key: String): String {
    val value = optString(key)
    return if (value == "null") "" else value
}

fun JSONObject.strOrNull(key: String): String? = str(key).takeIf { it.isNotBlank() }

fun JSONArray?.objects(): List<JSONObject> {
    if (this == null) return emptyList()
    return (0 until length()).mapNotNull { optJSONObject(it) }
}

fun JSONArray?.strings(): List<String> {
    if (this == null) return emptyList()
    return (0 until length()).map { optString(it) }.filter { it.isNotBlank() && it != "null" }
}

/** 把 //、http:// 开头的图片地址统一成 https。 */
fun normalizeUrl(url: String?): String? {
    val value = url?.takeIf { it.isNotBlank() && it != "null" } ?: return null
    val absolute = if (value.startsWith("//")) "https:$value" else value
    return absolute.replaceFirst(Regex("^http://", RegexOption.IGNORE_CASE), "https://")
}
