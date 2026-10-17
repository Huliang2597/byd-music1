package com.auramusic.wiki.data

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import java.net.URI
import java.net.URLDecoder

/** 打开网易云链接：优先跳到网易云音乐 App，否则用浏览器。 */
object Links {
    private const val PACKAGE = "com.netease.cloudmusic"

    fun appTargets(url: String): List<String> {
        return try {
            var uri = URI(url)
            val host = uri.host ?: return emptyList()
            if (!uri.scheme.equals("https", true) || uri.userInfo != null || (uri.port != -1 && uri.port != 443)) return emptyList()
            if (!host.equals("music.163.com", true) && !host.equals("y.music.163.com", true)) return emptyList()
            if (uri.fragment?.startsWith("/") == true) uri = URI("https://music.163.com" + uri.fragment)
            val kind = when (uri.path) {
                "/song", "/m/song" -> "song"
                "/artist", "/m/artist" -> "artist"
                "/user/home", "/m/user/home" -> "user"
                else -> return emptyList()
            }
            val id = uri.rawQuery?.split("&")?.firstNotNullOfOrNull { part ->
                val eq = part.indexOf('=')
                if (eq > 0 && URLDecoder.decode(part.substring(0, eq), "UTF-8") == "id") {
                    URLDecoder.decode(part.substring(eq + 1), "UTF-8").takeIf { it.matches(Regex("[1-9][0-9]{0,19}")) }
                } else {
                    null
                }
            } ?: return emptyList()
            listOf(
                "orpheus://$kind/$id",
                "https://music.163.com/" + (if (kind == "user") "user/home" else kind) + "?id=$id",
            )
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun open(context: Context, url: String) {
        for (target in appTargets(url)) {
            if (start(context, target, PACKAGE)) return
        }
        if (!start(context, url, null)) {
            Toast.makeText(context, "未找到可以打开链接的应用", Toast.LENGTH_SHORT).show()
        }
    }

    fun browse(context: Context, url: String) {
        if (!start(context, url, null)) Toast.makeText(context, "未找到可以打开链接的应用", Toast.LENGTH_SHORT).show()
    }

    private fun start(context: Context, url: String, pkg: String?): Boolean = try {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (pkg != null) intent.setPackage(pkg)
        context.startActivity(intent)
        true
    } catch (e: ActivityNotFoundException) {
        false
    } catch (e: SecurityException) {
        false
    }

    /** 从艺人 ID、艺人链接或 add-album?artistId= 链接中识别艺人 ID。 */
    fun parseArtistId(input: String): Long? {
        val text = input.trim()
        if (text.matches(Regex("[1-9][0-9]{0,19}"))) return text.toLongOrNull()
        Regex("(?i)artistId=([1-9][0-9]{0,19})").find(text)?.let { return it.groupValues[1].toLongOrNull() }
        return ArtistWiki.normalizeId(text)?.toLongOrNull()
    }
}
