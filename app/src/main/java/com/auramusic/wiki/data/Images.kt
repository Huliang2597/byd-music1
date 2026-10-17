package com.auramusic.wiki.data

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.RectF
import android.media.ExifInterface
import android.net.Uri
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import java.util.Locale

object Images {

    /** 艺人图片解码：校验格式与尺寸，按 EXIF 旋转。 */
    fun decodeArtist(bytes: ByteArray): Bitmap {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        if (bounds.outMimeType != "image/jpeg" && bounds.outMimeType != "image/png") throw IOException("请选择 JPG 或 PNG 图片")
        if (bounds.outWidth.toLong() * bounds.outHeight > 48_000_000) throw IOException("图片分辨率过大，请使用 4800 万像素以内的图片")
        if (bounds.outWidth < 400 || bounds.outHeight < 400) throw IOException("原图至少需要 640 × 520 像素")
        var sample = 1
        while (maxOf(bounds.outWidth, bounds.outHeight) / sample > 2400 &&
            minOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= 640
        ) {
            sample *= 2
        }
        if (bounds.outWidth.toLong() * bounds.outHeight / sample / sample > 16_000_000) {
            throw IOException("图片过长或解码尺寸过大，请缩小后再选择")
        }
        var bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample })
            ?: throw IOException("无法读取图片")
        val orientation = runCatching {
            ExifInterface(ByteArrayInputStream(bytes)).getAttributeInt(ExifInterface.TAG_ORIENTATION, 1)
        }.getOrDefault(1)
        val matrix = Matrix()
        when (orientation) {
            2 -> matrix.setScale(-1f, 1f)
            3 -> matrix.setRotate(180f)
            4 -> matrix.setScale(1f, -1f)
            5 -> { matrix.setRotate(90f); matrix.postScale(-1f, 1f) }
            6 -> matrix.setRotate(90f)
            7 -> { matrix.setRotate(270f); matrix.postScale(-1f, 1f) }
            8 -> matrix.setRotate(270f)
        }
        if (!matrix.isIdentity) {
            val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
            if (rotated != bitmap) bitmap.recycle()
            bitmap = rotated
        }
        if (bitmap.width < 640 || bitmap.height < 520) {
            bitmap.recycle()
            throw IOException("主页图片至少需要 640 × 520 像素，请选择更大的原图")
        }
        return bitmap
    }

    fun jpeg(bitmap: Bitmap): ByteArray {
        val out = ByteArrayOutputStream()
        if (!bitmap.compress(Bitmap.CompressFormat.JPEG, 92, out)) throw IOException("图片处理失败")
        return out.toByteArray()
    }

    /** 按源图坐标区域导出指定尺寸的 JPEG。 */
    fun export(source: Bitmap, region: RectF, width: Int, height: Int): ByteArray {
        val output = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        try {
            val canvas = Canvas(output)
            canvas.drawColor(android.graphics.Color.WHITE)
            val matrix = Matrix()
            matrix.setRectToRect(region, RectF(0f, 0f, width.toFloat(), height.toFloat()), Matrix.ScaleToFit.FILL)
            canvas.drawBitmap(source, matrix, Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG))
            return jpeg(output)
        } finally {
            output.recycle()
        }
    }

    class PreparedCover(val raw: File, val square: File, val preview: Bitmap)

    /** 专辑封面：保留原图，另外居中裁成正方形，并生成预览图。 */
    fun prepareCover(context: Context, uri: Uri, displayName: String): PreparedCover {
        val lower = displayName.lowercase(Locale.ROOT)
        if (!lower.endsWith(".jpg") && !lower.endsWith(".jpeg") && !lower.endsWith(".png")) {
            throw IOException("封面只支持 jpg / png")
        }
        val raw = File(context.cacheDir, "cover-raw-" + System.nanoTime())
        (context.contentResolver.openInputStream(uri) ?: throw IOException("无法读取文件")).use { input ->
            raw.outputStream().use { input.copyTo(it) }
        }
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(raw.path, bounds)
        if (minOf(bounds.outWidth, bounds.outHeight) < 320) {
            raw.delete()
            throw IOException("专辑图的像素不能小于320x320哦")
        }
        var sample = 1
        while (minOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= 1200) sample *= 2
        val decoded = BitmapFactory.decodeFile(raw.path, BitmapFactory.Options().apply { inSampleSize = sample })
            ?: throw IOException("无法读取图片")
        val edge = minOf(decoded.width, decoded.height)
        val square = Bitmap.createBitmap(decoded, (decoded.width - edge) / 2, (decoded.height - edge) / 2, edge, edge)
        val squareFile = File(context.cacheDir, "cover-1v1-" + System.nanoTime() + ".jpg")
        squareFile.outputStream().use { square.compress(Bitmap.CompressFormat.JPEG, 92, it) }
        val preview = Bitmap.createScaledBitmap(square, 360, 360, true)
        return PreparedCover(raw, squareFile, preview)
    }
}
