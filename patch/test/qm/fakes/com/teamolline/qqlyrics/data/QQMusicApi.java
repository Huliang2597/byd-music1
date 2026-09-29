package com.teamolline.qqlyrics.data;
import org.json.JSONObject;
/** Fake: official 请求走真正的 QmClient。 */
public final class QQMusicApi {
  public static boolean access$getOfficial$p(QQMusicApi a) { return true; }
  public static String access$getBase$p(QQMusicApi a) { return "https://u.y.qq.com"; }
  public static JSONObject access$getJson(QQMusicApi a, String url) { throw new RuntimeException(); }
  public static String access$encode(QQMusicApi a, String v) { return v; }
  public static String access$text(QQMusicApi a, JSONObject o, String[] keys) { return ""; }
  public static JSONObject access$officialRequest(QQMusicApi a, String module, String method, JSONObject p) throws Exception {
    return com.teamolline.qqlyrics.fix.QmClient.request(module, method, p);
  }
}
