package com.teamolline.qqlyrics.fix;

import android.util.Base64;

import com.teamolline.qqlyrics.data.ApiException;
import com.teamolline.qqlyrics.data.QQMusicApi;
import com.teamolline.qqlyrics.model.Lyrics;

import io.github.proify.qrckit.decrypt.QrcDecrypter;

import org.json.JSONObject;

import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 歌词获取与 QRC 处理的修复实现。
 *
 * 原版问题：
 * 1. 只有当接口返回 {@code "qrc": 1} 时才会去解密逐字歌词，但 QQ 音乐的 GetPlayLyricInfo
 *    并不稳定返回这个字段，导致逐字 QRC 被直接丢弃，只剩普通 LRC。
 *    现在改为解密后按内容判断是否为 QRC，并在拿不到时换参数重试。
 * 2. 歌词字段只按一种编码处理（加密 hex / base64 二选一），第三方接口返回的加密 QRC 不会被解密。
 *    现在自动识别 hex 加密、base64 与明文。
 * 3. QRC 转 LRC 只认带 XML 外壳的 QRC，裸 QRC（[起始,时长]字(起始,时长)）会得到空结果。
 * 4. LRC 时间戳输出为 [mm:ss.xxx]，不少车机/播放器只认 [mm:ss.xx]，会导致时间错乱。
 */
public final class LyricFix {

    private LyricFix() {
    }

    private static final Pattern QRC_LINE = Pattern.compile("^\\[(\\d+),(\\d+)\\](.*)$");
    private static final Pattern QRC_WORD = Pattern.compile("\\((\\d+),(\\d+)\\)");
    private static final Pattern QRC_CONTENT = Pattern.compile("LyricContent=\"([\\s\\S]*?)\"\\s*/>");
    private static final Pattern HEX = Pattern.compile("^[0-9A-Fa-f]+$");
    private static final Pattern LRC_STAMP = Pattern.compile("\\[\\d+:\\d{1,2}(?:[.:]\\d{1,3})?\\]");
    private static final Pattern META = Pattern.compile("^\\[(ti|ar|al|by):(.*)\\]$", Pattern.CASE_INSENSITIVE);

    // ---------------------------------------------------------------- fetching

    /** 替换 QQMusicApi.lyrics 协程体。 */
    public static Lyrics fetch(QQMusicApi api, String mid, String id) throws Exception {
        if (!QQMusicApi.access$getOfficial$p(api)) {
            return fetchThirdParty(api, mid);
        }
        return fetchOfficial(api, mid, id);
    }

    private static Lyrics fetchThirdParty(QQMusicApi api, String mid) {
        String base = QQMusicApi.access$getBase$p(api);
        JSONObject root = QQMusicApi.access$getJson(api,
                base + "/api/lyric?mid=" + QQMusicApi.access$encode(api, mid) + "&qrc=1&trans=1&roma=1");
        JSONObject data = root.optJSONObject("data");
        if (data != null) {
            root = data;
        }
        String qrc = decodeField(QQMusicApi.access$text(api, root, new String[]{"qrc", "qrc_lyric"}));
        String lrc = decodeField(QQMusicApi.access$text(api, root, new String[]{"lyric", "lrc", "orig"}));
        String trans = decodeField(QQMusicApi.access$text(api, root, new String[]{"trans", "tlyric", "translation"}));
        String roma = decodeField(QQMusicApi.access$text(api, root, new String[]{"roma", "romalrc", "romanization"}));
        if (!isQrc(qrc)) {
            if (isQrc(lrc)) {
                qrc = lrc;
                lrc = "";
            } else {
                qrc = "";
            }
        }
        return new Lyrics(qrc, lrc, trans, roma);
    }

    private static Lyrics fetchOfficial(QQMusicApi api, String mid, String id) throws Exception {
        String qrc = "";
        String lrc = "";
        String trans = "";
        String roma = "";
        boolean anySuccess = false;
        Throwable lastError = null;

        // 逐字歌词：不同参数组合依次尝试，拿到 QRC 就停止。
        int[] types = {0, -1, 1};
        for (int type : types) {
            JSONObject data;
            try {
                data = officialLyric(api, mid, id, true, type);
            } catch (Throwable t) {
                lastError = t;
                if (!(t instanceof ApiException)) {
                    break; // 网络错误：换参数也没用
                }
                continue;
            }
            anySuccess = true;
            String lyric = decodeField(data.optString("lyric"));
            String t = decodeField(data.optString("trans"));
            String r = decodeField(data.optString("roma"));
            if (isQrc(lyric)) {
                qrc = lyric;
                trans = t;
                roma = r;
                break;
            }
            if (isBlank(lrc) && looksLikeLrc(lyric)) {
                lrc = lyric;
            }
            if (isBlank(trans)) {
                trans = t;
            }
            if (isBlank(roma)) {
                roma = r;
            }
        }

        // 普通 LRC（明文逐行歌词）。
        try {
            JSONObject data = officialLyric(api, mid, id, false, 0);
            anySuccess = true;
            String lyric = decodeField(data.optString("lyric"));
            if (isQrc(lyric) && isBlank(qrc)) {
                qrc = lyric;
            } else if (!isBlank(lyric) && !isQrc(lyric)) {
                lrc = lyric;
            }
            if (isBlank(trans)) {
                trans = decodeField(data.optString("trans"));
            }
            if (isBlank(roma)) {
                roma = decodeField(data.optString("roma"));
            }
        } catch (Throwable t) {
            if (lastError == null) {
                lastError = t;
            }
        }

        if (!anySuccess) {
            String message = lastError != null ? lastError.getMessage() : null;
            throw new ApiException("歌词请求失败：" + (isBlank(message) ? "服务不可用" : message));
        }
        if (isBlank(lrc) && !isBlank(qrc)) {
            lrc = qrcToLrc(qrc);
        }
        return new Lyrics(qrc, lrc, trans, roma);
    }

    private static JSONObject officialLyric(QQMusicApi api, String mid, String id, boolean qrc, int type) throws Exception {
        long songId = 0L;
        if (id != null) {
            try {
                songId = Long.parseLong(id.trim());
            } catch (NumberFormatException ignored) {
                songId = 0L;
            }
        }
        JSONObject param = new JSONObject();
        param.put("songMID", mid == null ? "" : mid)
                .put("songID", songId)
                .put("format", "json")
                .put("crypt", qrc ? 1 : 0)
                .put("ct", 19)
                .put("cv", 1873)
                .put("interval", 0)
                .put("lrc_t", 0)
                .put("qrc", qrc ? 1 : 0)
                .put("qrc_t", 0)
                .put("roma", 1)
                .put("roma_t", 0)
                .put("trans", 1)
                .put("trans_t", 0)
                .put("type", type);
        return QQMusicApi.access$officialRequest(api, "music.musichallSong.PlayLyricInfo", "GetPlayLyricInfo", param);
    }

    // ---------------------------------------------------------------- decoding

    /** 自动识别歌词字段编码：QQ 加密 hex、base64 或明文。 */
    public static String decodeField(String raw) {
        if (raw == null) {
            return "";
        }
        String s = raw.trim();
        if (s.isEmpty() || "null".equals(s)) {
            return "";
        }
        if (s.length() >= 16 && s.length() % 2 == 0 && HEX.matcher(s).matches()) {
            String decrypted = QrcDecrypter.INSTANCE.decrypt(s);
            if (decrypted != null && !isBlank(decrypted)) {
                return stripBom(decrypted);
            }
        }
        if (looksLikeText(s)) {
            return stripBom(s);
        }
        try {
            byte[] bytes = Base64.decode(s, Base64.DEFAULT);
            String decoded = strictUtf8(bytes);
            if (decoded != null) {
                decoded = stripBom(decoded);
                // base64 里偶尔还是加密 hex
                String inner = decoded.trim();
                if (inner.length() >= 16 && inner.length() % 2 == 0 && HEX.matcher(inner).matches()) {
                    String decrypted = QrcDecrypter.INSTANCE.decrypt(inner);
                    if (decrypted != null && !isBlank(decrypted)) {
                        return stripBom(decrypted);
                    }
                }
                return decoded;
            }
        } catch (Throwable ignored) {
            // fall through
        }
        return "";
    }

    private static boolean looksLikeText(String s) {
        return s.indexOf('[') >= 0 || s.indexOf('<') >= 0 || s.indexOf('\n') >= 0;
    }

    private static String strictUtf8(byte[] bytes) {
        try {
            return StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(bytes))
                    .toString();
        } catch (CharacterCodingException e) {
            return null;
        }
    }

    private static String stripBom(String s) {
        return s.startsWith("\uFEFF") ? s.substring(1) : s;
    }

    // ---------------------------------------------------------------- QRC helpers

    /** 是否为逐字 QRC（XML 外壳或裸 QRC 均可）。 */
    public static boolean isQrc(String text) {
        if (text == null || isBlank(text)) {
            return false;
        }
        String body = qrcBody(text);
        for (String line : body.split("\\r?\\n|\\r")) {
            Matcher m = QRC_LINE.matcher(line.trim());
            if (m.matches() && QRC_WORD.matcher(m.group(3)).find()) {
                return true;
            }
        }
        return false;
    }

    private static boolean looksLikeLrc(String text) {
        return text != null && LRC_STAMP.matcher(text).find();
    }

    /** 取出 QRC 正文（去掉 XML 外壳并反转义）。 */
    public static String qrcBody(String text) {
        Matcher m = QRC_CONTENT.matcher(text);
        if (!m.find()) {
            return text;
        }
        return unescapeXml(m.group(1));
    }

    private static String unescapeXml(String s) {
        return s.replace("&quot;", "\"")
                .replace("&apos;", "'")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&#13;", "\r")
                .replace("&#10;", "\n")
                .replace("&amp;", "&");
    }

    private static String escapeXml(String s) {
        return s.replace("&", "&amp;")
                .replace("\"", "&quot;")
                .replace("<", "&lt;")
                .replace(">", "&gt;");
    }

    /** QRC → 逐行 LRC（[mm:ss.xx]），保留 ti/ar/al/by 标签。 */
    public static String qrcToLrc(String qrc) {
        if (qrc == null || isBlank(qrc)) {
            return "";
        }
        String body = qrcBody(qrc);
        StringBuilder sb = new StringBuilder();
        for (String raw : body.split("\\r?\\n|\\r")) {
            String line = raw.trim();
            if (line.isEmpty()) {
                continue;
            }
            Matcher meta = META.matcher(line);
            if (meta.matches()) {
                if (!isBlank(meta.group(2))) {
                    sb.append(line).append('\n');
                }
                continue;
            }
            Matcher m = QRC_LINE.matcher(line);
            if (!m.matches()) {
                continue;
            }
            long start;
            try {
                start = Long.parseLong(m.group(1));
            } catch (NumberFormatException e) {
                continue;
            }
            String words = QRC_WORD.matcher(m.group(3)).replaceAll("").trim();
            if (words.isEmpty()) {
                continue;
            }
            sb.append('[').append(formatTime(start)).append(']').append(words).append('\n');
        }
        return sb.toString().trim();
    }

    /** 预览/合并用：QRC 转成 LRC，并去掉翻译里的 “//” 占位行。 */
    public static String readableTrack(String track) {
        if (track == null) {
            return "";
        }
        String text = isQrc(track) ? qrcToLrc(track) : track;
        StringBuilder sb = new StringBuilder();
        for (String line : text.split("\\r?\\n|\\r")) {
            String content = LRC_STAMP.matcher(line).replaceAll("").trim();
            if ("//".equals(content)) {
                continue;
            }
            sb.append(line).append('\n');
        }
        return sb.toString().trim();
    }

    /** 标准 LRC 时间戳 mm:ss.xx（百分秒）。 */
    public static String formatTime(long millis) {
        if (millis < 0) {
            millis = 0;
        }
        long centis = (millis + 5) / 10;
        long minutes = centis / 6000;
        long seconds = (centis / 100) % 60;
        long fraction = centis % 100;
        return String.format(Locale.ROOT, "%02d:%02d.%02d", minutes, seconds, fraction);
    }

    /** 导出前整理内容：QRC 保证为完整的 QRC XML 文件。 */
    public static String prepareExport(String extension, String content) {
        if (content == null) {
            return "";
        }
        if (!"qrc".equalsIgnoreCase(extension)) {
            return content;
        }
        String text = stripBom(content.trim());
        if (text.contains("<QrcInfos") && text.contains("LyricContent=")) {
            return text;
        }
        if (!isQrc(text)) {
            return content;
        }
        String body = qrcBody(text).replace("\r\n", "\n").replace("\r", "\n").trim();
        return "<?xml version=\"1.0\" encoding=\"utf-8\"?>\r\n"
                + "<QrcInfos>\r\n"
                + "<QrcHeadInfo SaveTime=\"" + (System.currentTimeMillis() / 1000) + "\" Version=\"100\"/>\r\n"
                + "<LyricInfo LyricCount=\"1\">\r\n"
                + "<Lyric_1 LyricType=\"1\" LyricContent=\"" + escapeXml(body).replace("\n", "\r\n") + "\r\n\"/>\r\n"
                + "</LyricInfo>\r\n"
                + "</QrcInfos>";
    }

    private static boolean isBlank(String s) {
        return s == null || s.trim().isEmpty();
    }
}
