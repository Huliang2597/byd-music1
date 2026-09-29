import com.teamolline.qqlyrics.fix.QmClient;
import com.teamolline.qqlyrics.fix.LyricFix;
import com.teamolline.qqlyrics.model.Lyrics;
import org.json.*;
import java.nio.file.*;

public class QmClientTest {
  static int fails = 0;
  static void eq(String n, Object e, Object a) { if (!String.valueOf(e).equals(String.valueOf(a))) { fails++; System.out.println("FAIL " + n + "\n  expected: " + e + "\n  actual:   " + a); } else System.out.println("ok   " + n); }
  static String b64(String s) throws Exception { return java.util.Base64.getEncoder().encodeToString(s.getBytes("UTF-8")); }
  public static void main(String[] a) throws Exception {
    String xml = new String(Files.readAllBytes(Paths.get(a[0])), "UTF-8");
    JSONObject data = QmClient.request("music.search.SearchCgiService", "DoSearchForQQMusicDesktop",
        new JSONObject().put("query", "ÞULE").put("search_type", 0).put("page_num", 1).put("num_per_page", 12));
    JSONObject first = data.getJSONObject("body").getJSONObject("song").getJSONArray("list").getJSONObject(0);
    eq("search mapped to body.song.list", "M1", first.getString("mid"));

    Lyrics l = LyricFix.fetch(null, "M1", "");
    eq("lyrics qrc via qqmusiclight", xml, l.qrc);
    Lyrics l2 = LyricFix.fetch(null, "M2", "");
    eq("lyrics for song not in cache (detail lookup)", xml, l2.qrc);

    java.util.List<String> log = Files.readAllLines(Paths.get(a[1]));
    JSONObject session = new JSONObject(log.get(0)).getJSONObject("body");
    eq("first call GetSession", "GetSession", session.getJSONObject("request").getString("method"));
    JSONObject search = new JSONObject(log.get(1));
    eq("search method", "DoSearchForQQMusicLite", search.getJSONObject("body").getJSONObject("request").getString("method"));
    eq("comm uid/sid", "u1/s1", search.getJSONObject("body").getJSONObject("comm").getString("uid") + "/" + search.getJSONObject("body").getJSONObject("comm").getString("sid"));
    eq("cookie", "tmeLoginType=-1;", search.getJSONObject("headers").getString("Cookie"));
    eq("user agent", "okhttp/3.14.9", search.getJSONObject("headers").getString("User-Agent"));
    eq("search query", "ÞULE", search.getJSONObject("body").getJSONObject("request").getJSONObject("param").getString("query"));
    JSONObject lyric = new JSONObject(log.get(2)).getJSONObject("body").getJSONObject("request").getJSONObject("param");
    eq("lyric songID from cache", 123, lyric.getLong("songID"));
    eq("lyric songName", b64("晴天"), lyric.getString("songName"));
    eq("lyric singerName", b64("周杰伦/B"), lyric.getString("singerName"));
    eq("lyric albumName", b64("叶惠美"), lyric.getString("albumName"));
    eq("lyric interval", 269, lyric.getInt("interval"));
    eq("lyric cv", 2111, lyric.getInt("cv"));
    boolean detail = false; long id2 = 0;
    for (String line : log) { JSONObject r = new JSONObject(line).getJSONObject("body").getJSONObject("request");
      if (r.getString("method").equals("get_song_detail_yqq")) detail = true;
      if (r.getString("method").equals("GetPlayLyricInfo") && "M2".equals(r.getJSONObject("param").optString("songMID"))) id2 = r.getJSONObject("param").getLong("songID"); }
    eq("detail looked up for uncached song", true, detail);
    eq("songID filled from detail", 456, id2);
    System.out.println(fails == 0 ? "ALL PASSED" : fails + " FAILED"); System.exit(fails);
  }
}
