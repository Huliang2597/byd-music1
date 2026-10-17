package com.auramusic.wiki.data

import java.math.BigInteger
import java.net.URLEncoder
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.SecretKeySpec
import org.json.JSONObject

/** 网易云 weapi / eapi 参数加密。 */
object NeteaseCrypto {
    private const val ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    private const val PRESET_KEY = "0CoJUm6Qyw8W8jud"
    private const val IV = "0102030405060708"
    private const val EAPI_KEY = "e82ckenh8dichen8"
    private val MODULUS = BigInteger(
        "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7",
        16,
    )
    private val EXPONENT = BigInteger("010001", 16)
    private val random = SecureRandom()

    data class WeapiForm(val params: String, val encSecKey: String) {
        fun encoded(): String =
            "params=" + URLEncoder.encode(params, "UTF-8") + "&encSecKey=" + encSecKey
    }

    fun weapi(payload: JSONObject): WeapiForm {
        val secret = CharArray(16) { ALPHABET[random.nextInt(ALPHABET.length)] }.concatToString()
        val params = aesCbc(aesCbc(payload.toString(), PRESET_KEY), secret)
        val encSecKey = BigInteger(1, secret.reversed().toByteArray(Charsets.UTF_8))
            .modPow(EXPONENT, MODULUS)
            .toString(16)
            .padStart(256, '0')
        return WeapiForm(params, encSecKey)
    }

    /** 返回 eapi 的 params 参数（十六进制大写）。 */
    fun eapi(path: String, payload: String): String {
        val digest = md5Hex("nobody${path}use${payload}md5forencrypt".toByteArray(Charsets.UTF_8))
        val data = "$path-36cd479b6b5-$payload-36cd479b6b5-$digest"
        val cipher = Cipher.getInstance("AES/ECB/PKCS5Padding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(EAPI_KEY.toByteArray(Charsets.UTF_8), "AES"))
        return cipher.doFinal(data.toByteArray(Charsets.UTF_8)).joinToString("") { "%02X".format(it) }
    }

    fun md5Hex(bytes: ByteArray): String =
        MessageDigest.getInstance("MD5").digest(bytes).joinToString("") { "%02x".format(it) }

    private fun aesCbc(text: String, key: String): String {
        val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
        cipher.init(
            Cipher.ENCRYPT_MODE,
            SecretKeySpec(key.toByteArray(Charsets.UTF_8), "AES"),
            IvParameterSpec(IV.toByteArray(Charsets.UTF_8)),
        )
        return Base64.getEncoder().encodeToString(cipher.doFinal(text.toByteArray(Charsets.UTF_8)))
    }
}
