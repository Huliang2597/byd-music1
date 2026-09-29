package com.teamolline.qqlyrics.fix;

import android.util.Base64;

import com.teamolline.qqlyrics.data.ApiException;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * QQ 音乐请求（替换 QQMusicApi.officialRequest）。
 *
 * 原版用桌面版参数直接调用 DoSearchForQQMusicDesktop，现在会返回 2001。
 * 搜索、歌曲信息、歌词都改为依次尝试多个来源，任一成功即可：
 * <ul>
 *   <li>QQ 音乐简洁版（qqmusiclight）接口，参考 https://github.com/chenmozhijin/LDDC</li>
 *   <li>y.qq.com 网页版签名接口（musics.fcg + zzc 签名），签名算法参考 https://github.com/luren-dc/QQMusicApi</li>
 *   <li>c.y.qq.com 旧版接口，参考 https://github.com/WXRIW/Lyricify-Lyrics-Helper</li>
 * </ul>
 * 全部失败时，错误信息会列出每个来源的失败原因。
 */
public final class QmClient {

    private QmClient() {
    }

    public static final String VERSION = "修复版 v3";

    private static final String URL_MUSICU = "https://u.y.qq.com/cgi-bin/musicu.fcg";
    private static final String URL_MUSICS = "https://u.y.qq.com/cgi-bin/musics.fcg";
    private static final String BROWSER_UA =
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";
    private static final Random RANDOM = new Random();
    private static final Object LOCK = new Object();

    private static JSONObject session;
    /** mid / id → 歌曲信息（mid, id, title, singer, album, interval）。 */
    private static final Map<String, JSONObject> SONGS = new HashMap<>();

    /** 替换 QQMusicApi.officialRequest(module, method, param)，返回 data。 */
    public static JSONObject request(String module, String method, JSONObject param) throws Exception {
        if ("music.search.SearchCgiService".equals(module) && "DoSearchForQQMusicDesktop".equals(method)) {
            return search(param.optString("query"));
        }
        if ("music.pf_song_detail_svr".equals(module)) {
            JSONObject info = songInfo(param.optString("song_mid"), param.optLong("song_id"));
            JSONObject track = info == null ? null : new JSONObject()
                    .put("mid", info.optString("mid"))
                    .put("id", info.optLong("id"))
                    .put("title", info.optString("title"))
                    .put("singer", singerArray(info.optString("singer")))
                    .put("album", new JSONObject().put("name", info.optString("album")))
                    .put("interval", info.optInt("interval"));
            JSONObject data = new JSONObject();
            if (track != null) {
                data.put("track_info", track);
            }
            return data;
        }
        if ("music.musichallSong.PlayLyricInfo".equals(module) && "GetPlayLyricInfo".equals(method)) {
            enrichLyricParam(param);
        }
        return lite(module, method, param);
    }

    // ================================================================ search

    private static JSONObject search(String query) throws Exception {
        List<String> errors = new ArrayList<>();
        JSONArray items = null;
        for (int source = 0; source < 4 && (items == null || items.length() == 0); source++) {
            try {
                switch (source) {
                    case 0:
                        items = searchLite(query);
                        break;
                    case 1:
                        items = searchWeb(query);
                        break;
                    case 2:
                        items = searchClientCp(query);
                        break;
                    default:
                        items = searchSmartbox(query);
                        break;
                }
                if (items == null || items.length() == 0) {
                    errors.add(SEARCH_NAMES[source] + "：无结果");
                }
            } catch (Throwable t) {
                errors.add(SEARCH_NAMES[source] + "：" + describe(t));
                items = null;
            }
        }
        if (items == null || items.length() == 0) {
            boolean allEmpty = true;
            for (String e : errors) {
                if (!e.endsWith("无结果")) {
                    allEmpty = false;
                    break;
                }
            }
            if (allEmpty) {
                items = new JSONArray();
            } else {
                throw new ApiException("搜索失败（" + VERSION + "）\n" + join(errors));
            }
        }
        JSONArray normalized = new JSONArray();
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = normalizeSong(items.optJSONObject(i));
            if (item != null) {
                remember(item);
                normalized.put(item);
            }
        }
        // 原版从 body.song.list 读取结果
        return new JSONObject().put("body", new JSONObject().put("song", new JSONObject().put("list", normalized)));
    }

    private static final String[] SEARCH_NAMES = {"简洁版接口", "网页版接口", "旧版搜索", "快速搜索"};

    private static JSONArray searchLite(String query) throws Exception {
        JSONObject param = new JSONObject()
                .put("search_id", searchId())
                .put("remoteplace", "search.android.keyboard")
                .put("query", query)
                .put("search_type", 0)
                .put("num_per_page", 20)
                .put("page_num", 1)
                .put("highlight", 0)
                .put("nqc_flag", 0)
                .put("page_id", 1)
                .put("grp", 1);
        JSONObject body = lite("music.search.SearchCgiService", "DoSearchForQQMusicLite", param).optJSONObject("body");
        if (body == null) {
            return null;
        }
        JSONArray items = body.optJSONArray("item_song");
        if (items == null && body.optJSONObject("song") != null) {
            items = body.optJSONObject("song").optJSONArray("list");
        }
        return items;
    }

    private static JSONArray searchWeb(String query) throws Exception {
        JSONObject param = new JSONObject()
                .put("remoteplace", "txt.yqq.top")
                .put("searchid", searchId())
                .put("search_type", 0)
                .put("query", query)
                .put("page_num", 1)
                .put("num_per_page", 20);
        JSONObject body = web("music.search.SearchCgiService", "DoSearchForQQMusicDesktop", param).optJSONObject("body");
        JSONObject song = body == null ? null : body.optJSONObject("song");
        return song == null ? null : song.optJSONArray("list");
    }

    private static JSONArray searchClientCp(String query) throws Exception {
        String url = "https://c.y.qq.com/soso/fcgi-bin/client_search_cp?new_json=1&cr=1&t=0&p=1&n=20&format=json"
                + "&inCharset=utf8&outCharset=utf-8&w=" + URLEncoder.encode(query, "UTF-8");
        JSONObject root = new JSONObject(stripJsonp(get(url, "https://y.qq.com/")));
        checkCode(root, "code");
        JSONObject data = root.optJSONObject("data");
        JSONObject song = data == null ? null : data.optJSONObject("song");
        return song == null ? null : song.optJSONArray("list");
    }

    private static JSONArray searchSmartbox(String query) throws Exception {
        String url = "https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg?format=json&inCharset=utf8&outCharset=utf-8&key="
                + URLEncoder.encode(query, "UTF-8");
        JSONObject root = new JSONObject(stripJsonp(get(url, "https://y.qq.com/")));
        checkCode(root, "code");
        JSONObject data = root.optJSONObject("data");
        JSONObject song = data == null ? null : data.optJSONObject("song");
        return song == null ? null : song.optJSONArray("itemlist");
    }

    /** 统一成原版 toSong 能解析的格式：title, mid, id, singer[{name}], album{name}, interval。 */
    private static JSONObject normalizeSong(JSONObject item) throws Exception {
        if (item == null) {
            return null;
        }
        String mid = first(item, "mid", "songmid");
        long id = item.optLong("id");
        if (id <= 0) {
            id = item.optLong("songid");
        }
        String title = first(item, "title", "name", "songname");
        if (title.isEmpty() || (mid.isEmpty() && id <= 0)) {
            return null;
        }
        JSONArray singers = item.optJSONArray("singer");
        if (singers == null) {
            singers = singerArray(first(item, "singer", "singername"));
        }
        JSONObject albumObj = item.optJSONObject("album");
        String album = albumObj != null ? albumObj.optString("name") : first(item, "albumname");
        return new JSONObject()
                .put("mid", mid)
                .put("id", id)
                .put("title", title)
                .put("singer", singers)
                .put("album", new JSONObject().put("name", album))
                .put("interval", item.optInt("interval"));
    }

    private static JSONArray singerArray(String names) throws Exception {
        JSONArray array = new JSONArray();
        if (names != null) {
            for (String name : names.split("/")) {
                if (!name.trim().isEmpty()) {
                    array.put(new JSONObject().put("name", name.trim()));
                }
            }
        }
        return array;
    }

    private static String first(JSONObject o, String... keys) {
        for (String k : keys) {
            Object v = o.opt(k);
            if (v instanceof String && !((String) v).isEmpty() && !"null".equals(v)) {
                return (String) v;
            }
        }
        return "";
    }

    private static String searchId() {
        long t = (RANDOM.nextInt(20) + 1) * 18014398509481984L;
        long n = (long) RANDOM.nextInt(4194305) * 4294967296L;
        long r = System.currentTimeMillis() % 86400000L;
        return String.valueOf(t + n + r);
    }

    // ================================================================ song info

    /** 取歌曲信息：缓存 → 简洁版详情接口 → 旧版单曲接口。 */
    public static JSONObject songInfo(String mid, long id) throws Exception {
        JSONObject info = lookup(mid, id);
        if (info != null) {
            return info;
        }
        if ((mid == null || mid.isEmpty()) && id <= 0) {
            throw new ApiException("无效的歌曲 ID");
        }
        List<String> errors = new ArrayList<>();
        try {
            JSONObject detail = new JSONObject();
            if (mid != null && !mid.isEmpty()) {
                detail.put("song_mid", mid);
            } else {
                detail.put("song_id", id);
            }
            JSONObject track = lite("music.pf_song_detail_svr", "get_song_detail_yqq", detail).optJSONObject("track_info");
            JSONObject item = normalizeSong(track);
            if (item != null) {
                remember(item);
                return lookup(mid, id);
            }
            errors.add("简洁版详情：无结果");
        } catch (Throwable t) {
            errors.add("简洁版详情：" + describe(t));
        }
        try {
            String key = mid != null && !mid.isEmpty() ? "songmid=" + URLEncoder.encode(mid, "UTF-8") : "songid=" + id;
            String url = "https://c.y.qq.com/v8/fcg-bin/fcg_play_single_song.fcg?tpl=yqq_song_detail&format=json"
                    + "&g_tk=5381&loginUin=0&hostUin=0&inCharset=utf8&outCharset=utf-8&notice=0&platform=yqq&needNewCode=0&" + key;
            JSONObject root = new JSONObject(stripJsonp(get(url, "https://y.qq.com/")));
            checkCode(root, "code");
            JSONArray data = root.optJSONArray("data");
            JSONObject item = normalizeSong(data == null ? null : data.optJSONObject(0));
            if (item != null) {
                remember(item);
                return lookup(mid, id);
            }
            errors.add("旧版单曲：无结果");
        } catch (Throwable t) {
            errors.add("旧版单曲：" + describe(t));
        }
        throw new ApiException("获取歌曲信息失败（" + VERSION + "）\n" + join(errors));
    }

    private static JSONObject lookup(String mid, long id) {
        synchronized (SONGS) {
            JSONObject info = mid != null && !mid.isEmpty() ? SONGS.get("mid:" + mid) : null;
            if (info == null && id > 0) {
                info = SONGS.get("id:" + id);
            }
            return info;
        }
    }

    private static void remember(JSONObject item) {
        try {
            String mid = item.optString("mid");
            long id = item.optLong("id");
            StringBuilder singers = new StringBuilder();
            JSONArray singerArray = item.optJSONArray("singer");
            if (singerArray != null) {
                for (int i = 0; i < singerArray.length(); i++) {
                    JSONObject singer = singerArray.optJSONObject(i);
                    String name = singer != null ? singer.optString("name") : "";
                    if (!name.isEmpty()) {
                        if (singers.length() > 0) {
                            singers.append('/');
                        }
                        singers.append(name);
                    }
                }
            }
            JSONObject album = item.optJSONObject("album");
            JSONObject info = new JSONObject()
                    .put("mid", mid)
                    .put("id", id)
                    .put("title", item.optString("title"))
                    .put("singer", singers.toString())
                    .put("album", album != null ? album.optString("name") : "")
                    .put("interval", item.optInt("interval"));
            synchronized (SONGS) {
                if (!mid.isEmpty()) {
                    SONGS.put("mid:" + mid, info);
                }
                if (id > 0) {
                    SONGS.put("id:" + id, info);
                }
            }
        } catch (Throwable ignored) {
            // 缓存失败不影响主流程
        }
    }

    // ================================================================ lyrics

    private static void enrichLyricParam(JSONObject param) throws Exception {
        String mid = param.optString("songMID");
        long id = param.optLong("songID");
        JSONObject info = null;
        try {
            info = songInfo(mid, id);
        } catch (Throwable ignored) {
            // 没有歌曲信息也继续请求
        }
        if (info != null) {
            if (id <= 0) {
                id = info.optLong("id");
            }
            param.put("songName", b64(info.optString("title")))
                    .put("singerName", b64(info.optString("singer")))
                    .put("albumName", b64(info.optString("album")))
                    .put("interval", info.optInt("interval"));
        }
        param.put("songID", id)
                .put("ct", 19)
                .put("cv", 2111);
    }

    private static String b64(String s) {
        return Base64.encodeToString(s.getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP);
    }

    private static final Pattern XML_NODE = Pattern.compile(
            "<(content|contentts|contentroma)>\\s*(?:<!\\[CDATA\\[)?([\\s\\S]*?)(?:\\]\\]>)?\\s*</\\1>");

    /**
     * 旧版逐字歌词下载（lyric_download.fcg），需要数字歌曲 ID。
     * 返回 {原文, 翻译, 罗马音} 的原始字段（通常是加密 hex）。
     */
    public static String[] legacyLyrics(long id) throws Exception {
        String body = post("https://c.y.qq.com/qqmusic/fcgi-bin/lyric_download.fcg",
                "version=15&miniversion=82&lrctype=4&musicid=" + id,
                "application/x-www-form-urlencoded", "https://c.y.qq.com/", BROWSER_UA, null);
        body = body.replace("<!--", "").replace("-->", "");
        String[] result = {"", "", ""};
        Matcher m = XML_NODE.matcher(body);
        while (m.find()) {
            String value = m.group(2).trim();
            switch (m.group(1)) {
                case "content":
                    result[0] = value;
                    break;
                case "contentts":
                    result[1] = value;
                    break;
                default:
                    result[2] = value;
                    break;
            }
        }
        return result;
    }

    /** 网页版普通歌词（fcg_query_lyric_new.fcg）。返回 {原文, 翻译} 的原始字段（base64）。 */
    public static String[] webLyrics(String mid) throws Exception {
        String url = "https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg?format=json&g_tk=5381&loginUin=0"
                + "&hostUin=0&inCharset=utf8&outCharset=utf-8&notice=0&platform=yqq&needNewCode=0&pcachetime="
                + System.currentTimeMillis() + "&songmid=" + URLEncoder.encode(mid, "UTF-8");
        JSONObject root = new JSONObject(stripJsonp(get(url, "https://y.qq.com/portal/player.html")));
        checkCode(root, "code");
        return new String[]{root.optString("lyric"), root.optString("trans")};
    }

    // ================================================================ transports

    /** 简洁版（qqmusiclight）接口。 */
    private static JSONObject lite(String module, String method, JSONObject param) throws Exception {
        JSONObject comm = liteComm();
        try {
            return musicu(comm, module, method, param);
        } catch (ApiException e) {
            // 会话可能过期：换新会话重试一次
            synchronized (LOCK) {
                session = null;
            }
            return musicu(liteComm(), module, method, param);
        }
    }

    private static JSONObject liteComm() throws Exception {
        JSONObject s;
        synchronized (LOCK) {
            s = session;
        }
        if (s == null) {
            JSONObject param = new JSONObject().put("caller", 0).put("uid", "0").put("vkey", 0);
            JSONObject data;
            try {
                data = musicu(liteBaseComm(), "music.getSession.session", "GetSession", param);
            } catch (ApiException e) {
                throw new ApiException("会话 " + e.getMessage());
            }
            s = data.optJSONObject("session");
            if (s == null) {
                throw new ApiException("会话获取失败");
            }
            synchronized (LOCK) {
                session = s;
            }
        }
        return liteBaseComm()
                .put("uid", s.optString("uid"))
                .put("sid", s.optString("sid"))
                .put("userip", s.optString("userip"));
    }

    private static JSONObject liteBaseComm() throws Exception {
        return new JSONObject()
                .put("ct", 11)
                .put("cv", "1003006")
                .put("v", "1003006")
                .put("os_ver", "15")
                .put("phonetype", "24122RKC7C")
                .put("rom", "Redmi/miro/miro:15/AE3A.240806.005/OS2.0.105.0.VOMCNXM:user/release-keys")
                .put("tmeAppID", "qqmusiclight")
                .put("nettype", "NETWORK_WIFI")
                .put("udid", "0");
    }

    private static JSONObject musicu(JSONObject comm, String module, String method, JSONObject param) throws Exception {
        JSONObject payload = new JSONObject()
                .put("comm", comm)
                .put("request", new JSONObject()
                        .put("method", method)
                        .put("module", module)
                        .put("param", param));
        String text = post(endpoint(URL_MUSICU), payload.toString(), "application/json", null, "okhttp/3.14.9",
                "tmeLoginType=-1;");
        return unwrap(text, "request");
    }

    /** y.qq.com 网页版签名接口。 */
    private static JSONObject web(String module, String method, JSONObject param) throws Exception {
        JSONObject comm = new JSONObject()
                .put("cv", 4747474)
                .put("ct", 24)
                .put("format", "json")
                .put("inCharset", "utf-8")
                .put("outCharset", "utf-8")
                .put("notice", 0)
                .put("platform", "yqq.json")
                .put("needNewCode", 1)
                .put("uin", 0)
                .put("g_tk_new_20200303", 5381)
                .put("g_tk", 5381);
        JSONObject payload = new JSONObject()
                .put("comm", comm)
                .put("req_1", new JSONObject()
                        .put("module", module)
                        .put("method", method)
                        .put("param", param));
        String body = payload.toString();
        String url = endpoint(URL_MUSICS) + "?_=" + System.currentTimeMillis() + "&sign=" + zzcSign(body);
        String text = post(url, body, "application/json;charset=utf-8", "https://y.qq.com/", BROWSER_UA, null);
        return unwrap(text, "req_1");
    }

    /** 签名算法，移植自 QQMusicApi 的 qqmusic_api/algorithms/sign.py。 */
    static String zzcSign(String payload) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-1").digest(payload.getBytes(StandardCharsets.UTF_8));
        StringBuilder hex = new StringBuilder();
        for (byte b : digest) {
            hex.append(String.format(Locale.ROOT, "%02X", b & 0xff));
        }
        String h = hex.toString();
        int[] part1Indexes = {23, 14, 6, 36, 16, 7, 19};
        int[] part2Indexes = {16, 1, 32, 12, 19, 27, 8, 5};
        int[] scramble = {89, 39, 179, 150, 218, 82, 58, 252, 177, 52, 186, 123, 120, 64, 242, 133, 143, 161, 121, 179};
        StringBuilder part1 = new StringBuilder();
        for (int i : part1Indexes) {
            part1.append(h.charAt(i));
        }
        StringBuilder part2 = new StringBuilder();
        for (int i : part2Indexes) {
            part2.append(h.charAt(i));
        }
        byte[] part3 = new byte[20];
        for (int i = 0; i < scramble.length; i++) {
            part3[i] = (byte) (scramble[i] ^ Integer.parseInt(h.substring(i * 2, i * 2 + 2), 16));
        }
        String b64 = Base64.encodeToString(part3, Base64.NO_WRAP).replaceAll("[\\\\/+=]", "");
        return ("zzc" + part1 + b64 + part2).toLowerCase(Locale.ROOT);
    }

    private static JSONObject unwrap(String text, String key) throws Exception {
        JSONObject root;
        try {
            root = new JSONObject(text);
        } catch (Throwable t) {
            throw new ApiException("返回的不是 JSON");
        }
        int rootCode = root.optInt("code", 0);
        JSONObject result = root.optJSONObject(key);
        if (rootCode != 0 || result == null) {
            throw new ApiException("错误码 " + (rootCode != 0 ? rootCode : -1));
        }
        int resultCode = result.optInt("code", -1);
        if (resultCode != 0) {
            throw new ApiException("错误码 " + resultCode);
        }
        JSONObject data = result.optJSONObject("data");
        if (data == null) {
            throw new ApiException("没有返回数据");
        }
        return data;
    }

    private static void checkCode(JSONObject root, String key) throws ApiException {
        int code = root.optInt(key, 0);
        if (code != 0) {
            throw new ApiException("错误码 " + code);
        }
    }

    private static String stripJsonp(String text) {
        String t = text.trim();
        int start = t.indexOf('{');
        int end = t.lastIndexOf('}');
        if (start > 0 && end > start) {
            return t.substring(start, end + 1);
        }
        return t;
    }

    private static String endpoint(String url) {
        String override = System.getProperty("qqlyrics.endpoint");
        if (override == null || override.isEmpty()) {
            return url;
        }
        return override + url.substring(url.indexOf("/cgi-bin/"));
    }

    private static String get(String url, String referer) throws IOException {
        return http("GET", url, null, null, referer, BROWSER_UA, null);
    }

    private static String post(String url, String body, String contentType, String referer, String ua, String cookie)
            throws IOException {
        return http("POST", url, body.getBytes(StandardCharsets.UTF_8), contentType, referer, ua, cookie);
    }

    private static String http(String method, String url, byte[] body, String contentType, String referer, String ua,
                               String cookie) throws IOException {
        String override = System.getProperty("qqlyrics.endpoint");
        if (override != null && !override.isEmpty() && url.startsWith("https://c.y.qq.com/")) {
            url = override + url.substring("https://c.y.qq.com".length());
        }
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        try {
            connection.setRequestMethod(method);
            connection.setConnectTimeout(10000);
            connection.setReadTimeout(15000);
            connection.setRequestProperty("User-Agent", ua);
            connection.setRequestProperty("Accept", "application/json, text/plain, */*");
            if (referer != null) {
                connection.setRequestProperty("Referer", referer);
                connection.setRequestProperty("Origin", referer.startsWith("https://y.qq.com") ? "https://y.qq.com" : "https://c.y.qq.com");
            }
            if (cookie != null) {
                connection.setRequestProperty("Cookie", cookie);
            }
            if (body != null) {
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", contentType);
                OutputStream out = connection.getOutputStream();
                try {
                    out.write(body);
                } finally {
                    out.close();
                }
            }
            int code = connection.getResponseCode();
            InputStream in = code >= 200 && code < 300 ? connection.getInputStream() : connection.getErrorStream();
            String text = in != null ? readAll(in) : "";
            if (code < 200 || code >= 300) {
                throw new IOException("HTTP " + code);
            }
            return text;
        } finally {
            connection.disconnect();
        }
    }

    private static String readAll(InputStream in) throws IOException {
        try {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buffer = new byte[8192];
            int n;
            while ((n = in.read(buffer)) > 0) {
                out.write(buffer, 0, n);
            }
            return new String(out.toByteArray(), StandardCharsets.UTF_8);
        } finally {
            in.close();
        }
    }

    // ================================================================ misc

    static String describe(Throwable t) {
        if (t instanceof java.net.UnknownHostException) {
            return "无法连接（" + t.getMessage() + "）";
        }
        if (t instanceof java.net.SocketTimeoutException) {
            return "连接超时";
        }
        String message = t.getMessage();
        return message == null || message.isEmpty() ? t.getClass().getSimpleName() : message;
    }

    static String join(List<String> parts) {
        StringBuilder sb = new StringBuilder();
        for (String p : parts) {
            if (sb.length() > 0) {
                sb.append('\n');
            }
            sb.append("· ").append(p);
        }
        return sb.toString();
    }
}
