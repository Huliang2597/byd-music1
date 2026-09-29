import com.teamolline.qqlyrics.fix.QmClient;
import com.teamolline.qqlyrics.fix.LyricFix;
import com.teamolline.qqlyrics.model.Lyrics;
import org.json.*;
import java.nio.file.*;
import java.util.*;

/** 用法: QmClientTest <qrc.xml> <log.jsonl> <模式: lite_ok | lite_2001 | all_fail> */
public class QmClientTest {
  static int fails = 0;
  static void eq(String n, Object e, Object a) { if (!String.valueOf(e).equals(String.valueOf(a))) { fails++; System.out.println("FAIL " + n + "\n  expected: " + e + "\n  actual:   " + a); } else System.out.println("ok   " + n); }
  static String b64(String s) throws Exception { return java.util.Base64.getEncoder().encodeToString(s.getBytes("UTF-8")); }
  static JSONObject search(String q) throws Exception {
    return QmClient.request("music.search.SearchCgiService", "DoSearchForQQMusicDesktop",
        new JSONObject().put("query", q).put("search_type", 0).put("page_num", 1).put("num_per_page", 12));
  }
  static List<JSONObject> log(String path) throws Exception {
    List<JSONObject> out = new ArrayList<>();
    for (String line : Files.readAllLines(Paths.get(path))) out.add(new JSONObject(line));
    return out;
  }
  static List<JSONObject> requests(List<JSONObject> log, String method) {
    List<JSONObject> out = new ArrayList<>();
    for (JSONObject e : log) { JSONObject b = e.optJSONObject("body"); JSONObject r = b == null ? null : b.optJSONObject("request");
      if (r != null && r.getString("method").equals(method)) out.add(r); }
    return out;
  }
  static boolean hit(List<JSONObject> log, String pathSuffix) {
    for (JSONObject e : log) if (e.getString("path").endsWith(pathSuffix)) return true;
    return false;
  }

  public static void main(String[] a) throws Exception {
    String xml = new String(Files.readAllBytes(Paths.get(a[0])), "UTF-8");
    String mode = a[2];
    System.out.println("-- 模式 " + mode);
    if (mode.equals("all_fail")) {
      try { search("x"); eq("search throws", "exception", "none"); }
      catch (Exception e) {
        String m = e.getMessage();
        eq("search error lists version and every source", true, m.contains(QmClient.VERSION) && m.contains("简洁版接口") && m.contains("网页版接口") && m.contains("旧版搜索") && m.contains("快速搜索"));
        System.out.println("     " + m.replace("\n", "\n     "));
      }
      try { LyricFix.fetch(null, "M9", "999"); eq("lyrics throws", "exception", "none"); }
      catch (Exception e) {
        eq("lyrics error lists sources", true, e.getMessage().contains("旧版逐字接口") && e.getMessage().contains(QmClient.VERSION));
        System.out.println("     " + e.getMessage().replace("\n", "\n     "));
      }
    } else {
      JSONObject first = search("ÞULE").getJSONObject("body").getJSONObject("song").getJSONArray("list").getJSONObject(0);
      eq("search result mapped to body.song.list", "M1", first.getString("mid"));
      eq("search result has singers", "周杰伦", first.getJSONArray("singer").getJSONObject(0).getString("name"));
      Lyrics l = LyricFix.fetch(null, "M1", "");
      eq("qrc for searched song", xml, l.qrc);
      eq("lrc present", true, l.lrc.contains("故事的小"));
      Lyrics l2 = LyricFix.fetch(null, "M2", "");
      eq("qrc for song not in cache", xml, l2.qrc);
      List<JSONObject> log = log(a[1]);
      if (mode.equals("lite_ok")) {
        eq("session requested", 1, requests(log, "GetSession").size());
        JSONObject s = requests(log, "DoSearchForQQMusicLite").get(0);
        eq("search query", "ÞULE", s.getJSONObject("param").getString("query"));
        JSONObject p = requests(log, "GetPlayLyricInfo").get(0).getJSONObject("param");
        eq("lyric songID from cache", 123, p.getLong("songID"));
        eq("lyric songName", b64("晴天"), p.getString("songName"));
        eq("lyric singerName", b64("周杰伦/B"), p.getString("singerName"));
        eq("lyric albumName", b64("叶惠美"), p.getString("albumName"));
        eq("lyric interval", 269, p.getInt("interval"));
        eq("detail looked up for uncached song", 1, requests(log, "get_song_detail_yqq").size());
        eq("no legacy fallback needed", false, hit(log, "lyric_download.fcg"));
        JSONObject e0 = log.get(1);
        eq("okhttp UA + cookie", "okhttp/3.14.9|tmeLoginType=-1;", e0.getJSONObject("headers").getString("User-Agent") + "|" + e0.getJSONObject("headers").getString("Cookie"));
      } else {
        eq("signed web search accepted (no further fallback)", false, hit(log, "client_search_cp"));
        eq("legacy qrc download used", true, hit(log, "lyric_download.fcg"));
        eq("song detail via fcg_play_single_song", true, hit(log, "fcg_play_single_song.fcg"));
        boolean musicid456 = false;
        for (JSONObject e : log) if (e.getString("path").endsWith("lyric_download.fcg") && e.getString("body").contains("musicid=456")) musicid456 = true;
        eq("legacy download used id from song detail", true, musicid456);
      }
    }
    System.out.println(fails == 0 ? "ALL PASSED" : fails + " FAILED"); System.exit(fails);
  }
}
