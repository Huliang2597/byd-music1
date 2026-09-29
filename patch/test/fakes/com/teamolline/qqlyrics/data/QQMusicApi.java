package com.teamolline.qqlyrics.data;
import org.json.JSONObject;
import java.util.*;
/** Fake: scripted responses for GetPlayLyricInfo. */
public final class QQMusicApi {
  public static String qrcHex; public static String lrcB64; public static Integer qrcOnlyForType; public static boolean fail;
  public static List<String> calls = new ArrayList<>();
  public static boolean access$getOfficial$p(QQMusicApi a) { return true; }
  public static String access$getBase$p(QQMusicApi a) { return "https://u.y.qq.com"; }
  public static JSONObject access$getJson(QQMusicApi a, String url) { throw new RuntimeException(); }
  public static String access$encode(QQMusicApi a, String v) { return v; }
  public static String access$text(QQMusicApi a, JSONObject o, String[] keys) { return ""; }
  public static JSONObject access$officialRequest(QQMusicApi a, String module, String method, JSONObject p) throws ApiException {
    calls.add(p.toString());
    if (fail) throw new ApiException("网络错误");
    JSONObject r = new JSONObject();
    int crypt = p.getInt("crypt"); int type = p.getInt("type");
    if (crypt == 1) { // no "qrc" flag on purpose
      r.put("lyric", (qrcOnlyForType == null || qrcOnlyForType == type) ? qrcHex : "");
    } else { r.put("lyric", lrcB64); }
    r.put("trans", ""); r.put("roma", "");
    return r;
  }
}
