package com.teamolline.qqlyrics.fix;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.DocumentsContract;
import android.provider.MediaStore;
import android.widget.Toast;

import com.teamolline.qqlyrics.PendingExport;

import java.util.Locale;

/**
 * 保存文件时保证后缀是 .qrc / .lrc。
 *
 * 部分文件选择器（车机、定制 ROM）会把 application/octet-stream 文件命名成
 * “xxx.qrc.txt”“xxx.bin”“xxx.txt” 等，且不支持改名，原版只能提示用户手动改后缀。
 * 这里先尝试改名；改名失败时，在 Android 10+ 上改存到 下载/QQ歌词/ 目录并删除错名文件。
 */
public final class ExportFix {

    private ExportFix() {
    }

    private static final String FALLBACK_DIR = "QQ歌词";

    /** 替换 MainActivityKt.correctDocumentName。返回值是随后写入内容的 Uri。 */
    public static Uri correctDocumentName(Context context, Uri uri, PendingExport export) {
        String extension = export.getExtension().toLowerCase(Locale.ROOT);
        if ("txt".equals(extension)) {
            return uri;
        }
        ContentResolver resolver = context.getContentResolver();
        String current = documentName(resolver, uri);
        if (current == null || hasExtension(current, extension)) {
            return uri;
        }

        String target = stripWrongSuffix(current, extension);
        try {
            Uri renamed = DocumentsContract.renameDocument(resolver, uri, target);
            Uri result = renamed != null ? renamed : uri;
            String name = documentName(resolver, result);
            if (name != null && hasExtension(name, extension)) {
                return result;
            }
            uri = result;
        } catch (Throwable ignored) {
            // provider 不支持改名，走下面的兜底
        }

        if (Build.VERSION.SDK_INT >= 29) {
            try {
                ContentValues values = new ContentValues();
                values.put(MediaStore.MediaColumns.DISPLAY_NAME, export.getFilename());
                values.put(MediaStore.MediaColumns.MIME_TYPE, "application/octet-stream");
                values.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/" + FALLBACK_DIR);
                Uri created = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                if (created != null) {
                    String name = documentName(resolver, created);
                    if (name == null || hasExtension(name, extension)) {
                        try {
                            DocumentsContract.deleteDocument(resolver, uri);
                        } catch (Throwable ignored) {
                            // 删不掉就留着空文件
                        }
                        Toast.makeText(context,
                                "所选位置不支持 ." + extension + " 文件名，已改存到：下载/" + FALLBACK_DIR + "/"
                                        + (name != null ? name : export.getFilename()),
                                Toast.LENGTH_LONG).show();
                        return created;
                    }
                    try {
                        resolver.delete(created, null, null);
                    } catch (Throwable ignored) {
                        // ignore
                    }
                }
            } catch (Throwable ignored) {
                // 兜底失败则保持原 Uri，由原逻辑提示用户
            }
        }
        return uri;
    }

    private static boolean hasExtension(String name, String extension) {
        return name.toLowerCase(Locale.ROOT).endsWith("." + extension);
    }

    /** “歌名.qrc.txt” → “歌名.qrc”，“歌名.txt”/“歌名.bin”/“歌名” → “歌名.qrc”。 */
    static String stripWrongSuffix(String name, String extension) {
        String base = name;
        boolean changed = true;
        while (changed) {
            changed = false;
            String lower = base.toLowerCase(Locale.ROOT);
            for (String bad : new String[]{".txt", ".bin", ".octet-stream"}) {
                if (lower.endsWith(bad) && base.length() > bad.length()) {
                    base = base.substring(0, base.length() - bad.length());
                    changed = true;
                    break;
                }
            }
        }
        return hasExtension(base, extension) ? base : base + "." + extension;
    }

    private static String documentName(ContentResolver resolver, Uri uri) {
        Cursor cursor = null;
        try {
            cursor = resolver.query(uri, new String[]{"_display_name"}, null, null, null);
            if (cursor != null && cursor.moveToFirst()) {
                return cursor.getString(0);
            }
        } catch (Throwable ignored) {
            // ignore
        } finally {
            if (cursor != null) {
                try {
                    cursor.close();
                } catch (Throwable ignored) {
                    // ignore
                }
            }
        }
        return null;
    }
}
