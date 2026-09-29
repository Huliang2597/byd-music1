package com.teamolline.qqlyrics.fix;

import android.util.Base64;

import com.teamolline.qqlyrics.data.ApiException;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.Random;

/**
 * QQ 音乐请求（替换 QQMusicApi.officialRequest）。
 *
 * 原版用桌面版参数（ct=19）直接调用 DoSearchForQQMusicDesktop，现在会返回 2001。
 * 这里改用 QQ 音乐简洁版（qqmusiclight）的公共参数并先获取会话，
 * 做法参考 https://github.com/chenmozhijin/LDDC 的 LDDC/core/api/lyrics/qm.py。
 */
public final class QmClient {

    private QmClient() {
    }

    private static final String URL_MUSICU = "https://u.y.qq.com/cgi-bin/musicu.fcg";
    private static final Random RANDOM = new Random();
    private static final Object LOCK = new Object();

    private static JSONObject session;
    /** mid / id → 歌曲信息（title, singer, album, interval, id, mid），歌词请求需要。 */
    private static final Map<String, JSONObject> SONGS = new HashMap<>();

    /** 替换 QQMusicApi.officialRequest(module, method, param)，返回 data。 */
    public static JSONObject request(String module, String method, JSONObject param) throws Exception {
        if ("music.search.SearchCgiService".equals(module) && "DoSearchForQQMusicDesktop".equals(method)) {
            return search(param);
        }
        if ("music.musichallSong.PlayLyricInfo".equals(module) && "GetPlayLyricInfo".equals(method)) {
            enrichLyricParam(param);
        }
        JSONObject data = call(module, method, param);
        if ("music.pf_song_detail_svr".equals(module)) {
            JSONObject track = data.optJSONObject("track_info");
            if (track != null) {
                remember(track);
            }
        }
        return data;
    }

    // ---------------------------------------------------------------- search

    private static JSONObject search(JSONObject original) throws Exception {
        String query = original.optString("query");
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
        JSONObject data = call("music.search.SearchCgiService", "DoSearchForQQMusicLite", param);
        JSONObject body = data.optJSONObject("body");
        if (body == null) {
            body = new JSONObject();
            data.put("body", body);
        }
        JSONArray items = body.optJSONArray("item_song");
        if (items == null) {
            JSONObject song = body.optJSONObject("song");
            items = song != null ? song.optJSONArray("list") : null;
        }
        if (items == null) {
            items = new JSONArray();
        }
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.optJSONObject(i);
            if (item != null) {
                remember(item);
            }
        }
        // 原版从 body.song.list 读取结果
        body.put("song", new JSONObject().put("list", items));
        return data;
    }

    private static String searchId() {
        long t = (RANDOM.nextInt(20) + 1) * 18014398509481984L;
        long n = (long) RANDOM.nextInt(4194305) * 4294967296L;
        long r = System.currentTimeMillis() % 86400000L;
        return String.valueOf(t + n + r);
    }

    // ---------------------------------------------------------------- lyrics

    private static void enrichLyricParam(JSONObject param) throws Exception {
        String mid = param.optString("songMID");
        long id = param.optLong("songID");
        JSONObject info = lookup(mid, id);
        if (info == null && (!mid.isEmpty() || id > 0)) {
            try {
                JSONObject detail = new JSONObject();
                if (!mid.isEmpty()) {
                    detail.put("song_mid", mid);
                } else {
                    detail.put("song_id", id);
                }
                JSONObject track = call("music.pf_song_detail_svr", "get_song_detail_yqq", detail).optJSONObject("track_info");
                if (track != null) {
                    remember(track);
                }
            } catch (Throwable ignored) {
                // 查不到详情也继续请求歌词
            }
            info = lookup(mid, id);
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
            if (mid.isEmpty() && id <= 0) {
                return;
            }
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
            String title = item.optString("title");
            if (title.isEmpty()) {
                title = item.optString("name");
            }
            JSONObject info = new JSONObject()
                    .put("mid", mid)
                    .put("id", id)
                    .put("title", title)
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

    // ---------------------------------------------------------------- transport

    private static JSONObject call(String module, String method, JSONObject param) throws Exception {
        JSONObject comm = comm();
        try {
            return post(comm, module, method, param);
        } catch (ApiException e) {
            // 会话可能过期：换新会话重试一次
            synchronized (LOCK) {
                session = null;
            }
            return post(comm(), module, method, param);
        }
    }

    private static JSONObject comm() throws Exception {
        JSONObject s;
        synchronized (LOCK) {
            s = session;
        }
        if (s == null) {
            JSONObject param = new JSONObject().put("caller", 0).put("uid", "0").put("vkey", 0);
            JSONObject data = post(baseComm(), "music.getSession.session", "GetSession", param);
            s = data.optJSONObject("session");
            if (s == null) {
                throw new ApiException("QQ 音乐会话获取失败");
            }
            synchronized (LOCK) {
                session = s;
            }
        }
        return baseComm()
                .put("uid", s.optString("uid"))
                .put("sid", s.optString("sid"))
                .put("userip", s.optString("userip"));
    }

    private static JSONObject baseComm() throws Exception {
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

    private static JSONObject post(JSONObject comm, String module, String method, JSONObject param) throws Exception {
        JSONObject payload = new JSONObject()
                .put("comm", comm)
                .put("request", new JSONObject()
                        .put("method", method)
                        .put("module", module)
                        .put("param", param));
        byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);

        HttpURLConnection connection = (HttpURLConnection) new URL(System.getProperty("qqlyrics.endpoint", URL_MUSICU)).openConnection();
        String text;
        int code;
        try {
            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(12000);
            connection.setReadTimeout(18000);
            connection.setRequestProperty("Content-Type", "application/json");
            connection.setRequestProperty("Cookie", "tmeLoginType=-1;");
            connection.setRequestProperty("User-Agent", "okhttp/3.14.9");
            OutputStream out = connection.getOutputStream();
            try {
                out.write(body);
            } finally {
                out.close();
            }
            code = connection.getResponseCode();
            InputStream in = code >= 200 && code < 300 ? connection.getInputStream() : connection.getErrorStream();
            text = in != null ? readAll(in) : "";
        } finally {
            connection.disconnect();
        }
        if (code < 200 || code >= 300) {
            throw new java.io.IOException("服务返回 HTTP " + code);
        }
        JSONObject root;
        try {
            root = new JSONObject(text);
        } catch (Throwable t) {
            throw new ApiException("QQ 音乐没有返回有效 JSON");
        }
        int rootCode = root.optInt("code", 0);
        JSONObject result = root.optJSONObject("request");
        if (rootCode != 0 || result == null) {
            throw new ApiException("QQ 音乐接口错误（" + (rootCode != 0 ? rootCode : -1) + "）");
        }
        int resultCode = result.optInt("code", -1);
        if (resultCode != 0) {
            throw new ApiException("QQ 音乐接口错误（" + resultCode + "）");
        }
        JSONObject data = result.optJSONObject("data");
        if (data == null) {
            throw new ApiException("QQ 音乐没有返回数据");
        }
        return data;
    }

    private static String readAll(InputStream in) throws java.io.IOException {
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
}
