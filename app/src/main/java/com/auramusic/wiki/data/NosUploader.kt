package com.auramusic.wiki.data

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import java.io.File
import java.io.RandomAccessFile
import java.security.MessageDigest
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

/** 分片上传音频和图片到网易云 NOS。 */
class NosUploader(private val context: Context, private val session: NeteaseSession) {

    fun displayName(uri: Uri): String {
        if (uri.scheme == "file") return File(uri.path.orEmpty()).name.ifBlank { "file" }
        runCatching {
            context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
                if (c.moveToFirst() && !c.isNull(0)) return c.getString(0)
            }
        }
        return uri.lastPathSegment?.substringAfterLast('/')?.ifBlank { null } ?: "file"
    }

    /**
     * 上传文件，progress 取值 0..1。
     * 复制并计算 MD5 占 0~20%，申请凭证到 22%，其余为分片上传。
     */
    suspend fun upload(
        uri: Uri,
        kind: UploadKind,
        name: String? = null,
        progress: (Float) -> Unit = {},
    ): NosFile = withContext(Dispatchers.IO) {
        val cache = File(context.cacheDir, "nos-" + System.nanoTime())
        try {
            val fileName = name ?: displayName(uri)
            val md5 = copy(uri, cache) { progress(it * 0.2f) }
            val size = cache.length()
            if (size <= 0) throw WikiException("文件是空的")
            if (kind == UploadKind.AUDIO && size > 500L * 1024 * 1024) throw WikiException("音频大小超出500M")
            if (kind == UploadKind.IMAGE && size > 20L * 1024 * 1024) throw WikiException("原图要小于20M")
            val mime = mime(fileName, context.contentResolver.getType(uri), kind)
            val token = token(kind, fileName, size, md5)
            progress(0.22f)
            val bucket = token.str("bucket").ifBlank { if (kind == UploadKind.AUDIO) "ymusic" else "yyimgs" }
            val objectKey = token.str("objectKey")
            val nosToken = token.str("token")
            if (objectKey.isBlank() || nosToken.isBlank()) throw WikiException("获取上传凭证失败")
            send(cache, bucket, objectKey, nosToken, md5, mime) { progress(0.22f + it * 0.78f) }
            progress(1f)
            NosFile(fileName, size, mime, bucket, objectKey, token.str("docId"), token.str("resourceId"), md5)
        } finally {
            cache.delete()
        }
    }

    private suspend fun copy(uri: Uri, target: File, progress: (Float) -> Unit): String {
        val digest = MessageDigest.getInstance("MD5")
        val total = if (uri.scheme == "file") {
            File(uri.path.orEmpty()).length()
        } else {
            runCatching {
                context.contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { c ->
                    if (c.moveToFirst() && !c.isNull(0)) c.getLong(0) else -1L
                }
            }.getOrNull() ?: -1L
        }
        val input = context.contentResolver.openInputStream(uri) ?: throw WikiException("无法读取文件")
        input.use { stream ->
            target.outputStream().use { out ->
                val buffer = ByteArray(64 * 1024)
                var copied = 0L
                while (true) {
                    kotlinx.coroutines.currentCoroutineContext().ensureActive()
                    val read = stream.read(buffer)
                    if (read < 0) break
                    digest.update(buffer, 0, read)
                    out.write(buffer, 0, read)
                    copied += read
                    if (total > 0) progress((copied.toFloat() / total).coerceAtMost(1f))
                }
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private suspend fun token(kind: UploadKind, fileName: String, size: Long, md5: String): JSONObject {
        val url = when (kind) {
            UploadKind.AUDIO -> "https://music.163.com/api/nos/token/whalealloc".toHttpUrl().newBuilder()
                .addQueryParameter("filename", fileName)
                .addQueryParameter("fileSize", size.toString())
                .addQueryParameter("type", "audio")
                .addQueryParameter("bucket", "ymusic")
                .addQueryParameter("bizKey", "3a92052e")
                .addQueryParameter("md5", md5)
            UploadKind.IMAGE -> "https://music.163.com/api/nos/token/alloc".toHttpUrl().newBuilder()
                .addQueryParameter("filename", fileName)
                .addQueryParameter("ext", fileName.substringAfterLast('.', "jpg"))
                .addQueryParameter("type", "image")
                .addQueryParameter("bucket", "yyimgs")
                .addQueryParameter("local", "false")
                .addQueryParameter("nos_product", "0")
        }.build()
        val request = Request.Builder().url(url)
            .post(ByteArray(0).toRequestBody(null))
            .header("User-Agent", Http.CHROME_UA)
            .header("Referer", "https://music.163.com/st/wiki/")
            .header("Accept", "application/json")
            .header("Cookie", session.webCookie())
            .build()
        Http.api.newCall(request).await().use { response ->
            val json = runCatching { JSONObject(response.body?.string().orEmpty()) }.getOrNull()
                ?: throw WikiException("网易云请求失败（HTTP ${response.code}）")
            if (json.optInt("code", 200) == 301) throw WikiException("登录已失效，请重新登录")
            val data = json.optJSONObject("data") ?: json.optJSONObject("result")
            if (data != null && data.str("objectKey").isNotBlank()) return data
            throw WikiException(json.strOrNull("message") ?: json.strOrNull("msg") ?: "获取上传凭证失败")
        }
    }

    private suspend fun send(
        file: File,
        bucket: String,
        objectKey: String,
        token: String,
        md5: String,
        mime: String,
        progress: (Float) -> Unit,
    ) {
        val length = file.length()
        var offset = 0L
        var chunk = 256 * 1024
        var context: String? = null
        var attempt = 0
        var failures = 0
        RandomAccessFile(file, "r").use { raf ->
            while (true) {
                kotlinx.coroutines.currentCoroutineContext().ensureActive()
                val end = minOf(offset + chunk, length)
                val complete = end >= length
                val bytes = ByteArray((end - offset).toInt())
                raf.seek(offset)
                raf.readFully(bytes)
                val started = System.currentTimeMillis()
                // 偶数次尝试直传 NOS，失败后改走网易云代理，二者交替
                val direct = attempt % 2 == 0
                val url = (if (direct) "https://nosup-hz1.127.net/$bucket/$objectKey" else "https://music.163.com/web/proxy/nosupload")
                    .toHttpUrl().newBuilder()
                    .addQueryParameter("offset", offset.toString())
                    .addQueryParameter("complete", complete.toString())
                    .addQueryParameter("version", "1.0")
                    .apply { context?.let { addQueryParameter("context", it) } }
                    .addQueryParameter("objectkey", "$bucket/$objectKey")
                    .build()
                val request = Request.Builder().url(url)
                    .post(bytes.toRequestBody(mime.toMediaTypeOrNull()))
                    .header("x-nos-token", token)
                    .header("Content-MD5", md5)
                    .header("User-Agent", Http.CHROME_UA)
                    .build()
                val result = runCatching {
                    Http.api.newCall(request).await().use { response ->
                        val text = response.body?.string().orEmpty()
                        if (response.code !in 200..299) throw WikiException("上传失败（HTTP ${response.code}）$text")
                        JSONObject(text.ifBlank { "{}" })
                    }
                }
                val json = result.getOrNull()
                if (json == null) {
                    val error = result.exceptionOrNull()
                    if (error is kotlinx.coroutines.CancellationException) throw error
                    failures++
                    attempt++
                    if (failures > 10) throw error ?: WikiException("上传失败")
                    delay(500L * failures)
                    continue
                }
                failures = 0
                context = json.strOrNull("context") ?: context
                offset = if (json.has("offset")) json.optLong("offset") else end
                progress(if (length > 0) offset.toFloat() / length else 1f)
                if (complete && offset >= length) return
                val elapsed = System.currentTimeMillis() - started
                chunk = when {
                    elapsed > 30_000 -> maxOf(16 * 1024, chunk / 2)
                    elapsed < 50 -> minOf(10 * 1024 * 1024, chunk * 2)
                    elapsed < 1500 -> minOf(4 * 1024 * 1024, chunk * 2)
                    else -> chunk
                }
            }
        }
    }

    private fun mime(fileName: String, reported: String?, kind: UploadKind): String {
        val byExt = when (fileName.substringAfterLast('.', "").lowercase(Locale.ROOT)) {
            "mp3" -> "audio/mpeg"
            "flac" -> "audio/flac"
            "wav" -> "audio/wav"
            "ogg" -> "audio/ogg"
            "ape" -> "audio/ape"
            "m4a", "mp4", "aac" -> "audio/mp4"
            "jpg", "jpeg" -> "image/jpeg"
            "png" -> "image/png"
            else -> null
        }
        val normalized = when (reported) {
            "audio/mp3" -> "audio/mpeg"
            "audio/x-m4a" -> "audio/mp4"
            else -> reported
        }
        return byExt ?: normalized ?: if (kind == UploadKind.AUDIO) "audio/mpeg" else "image/jpeg"
    }
}
