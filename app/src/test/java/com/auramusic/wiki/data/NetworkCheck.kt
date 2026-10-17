package com.auramusic.wiki.data

import kotlinx.coroutines.runBlocking
import okhttp3.FormBody
import okhttp3.Request
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test

/** 手动运行的联网自检：-Pnetwork=true 时才执行。 */
class NetworkCheck {
    private val enabled = System.getProperty("network") == "true"

    @Test
    fun weapiQrKey() = runBlocking {
        assumeTrue(enabled)
        val key = NeteaseAuth.createQrKey()
        println("qr key: $key")
        assertTrue(key.isNotBlank())
    }

    @Test
    fun eapiSearch() = runBlocking {
        assumeTrue(enabled)
        val path = "/api/cloudsearch/pc"
        val payload = JSONObject().put("s", "七里香").put("type", "1").put("limit", "3").put("offset", "0")
            .put("header", JSONObject().put("os", "android").put("appver", "8.20.20").toString())
        val request = Request.Builder()
            .url("https://interface3.music.163.com/e" + path.removePrefix("/"))
            .post(FormBody.Builder().add("params", NeteaseCrypto.eapi(path, payload.toString())).build())
            .header("User-Agent", "NeteaseMusic/8.20.20.240716 (Linux; Android 14)")
            .header("Referer", "https://music.163.com/")
            .header("Cookie", "os=android; appver=8.20.20")
            .build()
        val json = Http.api.newCall(request).await().use { JSONObject(it.body!!.string()) }
        println("eapi: " + json.toString().take(300))
        assertEquals(200, json.optInt("code"))
    }

    @Test
    fun publicWiki() = runBlocking {
        assumeTrue(enabled)
        val json = PublicWiki.fetch("186016")
        println("wiki: " + json.toString().take(300))
        assertTrue(json.optBoolean("ok"))
    }

    @Test
    fun parsing() {
        assertEquals("186016", PublicWiki.normalizeId("https://music.163.com/song?id=186016&userid=1"))
        assertEquals("https://163cn.tv/abc123", PublicWiki.shortLink("分享 http://163cn.tv/abc123 来自网易云"))
        assertEquals(6452L, com.auramusic.wiki.data.Links.parseArtistId("https://music.163.com/#/wiki/add-album?artistId=6452"))
        assertEquals("6452", ArtistWiki.normalizeId("https://music.163.com/#/artist?id=6452"))
        assertEquals(
            "https://p1.music.126.net/a/b.jpg?param=256y256",
            PublicWiki.thumbnail("http://p1.music.126.net/a/b.jpg?param=40y40", 256),
        )
        val form = NeteaseCrypto.weapi(JSONObject().put("a", 1))
        assertEquals(256, form.encSecKey.length)
    }
}
