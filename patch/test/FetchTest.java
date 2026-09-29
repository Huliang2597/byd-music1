import com.teamolline.qqlyrics.data.QQMusicApi;
import com.teamolline.qqlyrics.fix.LyricFix;
import com.teamolline.qqlyrics.model.Lyrics;
import java.nio.file.*;
public class FetchTest {
  public static void main(String[] a) throws Exception {
    String xml = new String(Files.readAllBytes(Paths.get(a[0])), "UTF-8");
    QQMusicApi.qrcHex = new String(Files.readAllBytes(Paths.get(a[1])), "UTF-8").trim();
    QQMusicApi.lrcB64 = java.util.Base64.getEncoder().encodeToString("[00:01.00]故事的小\n".getBytes("UTF-8"));
    int fails = 0;
    Lyrics l = LyricFix.fetch(null, "0039MnYb0qxYhV", "97773");
    if (!xml.equals(l.qrc)) { fails++; System.out.println("FAIL qrc not detected without flag"); } else System.out.println("ok   qrc detected without \"qrc\" flag, calls=" + QQMusicApi.calls.size());
    if (!l.lrc.equals("[00:01.00]故事的小\n")) { fails++; System.out.println("FAIL lrc: " + l.lrc); } else System.out.println("ok   lrc");
    QQMusicApi.calls.clear(); QQMusicApi.qrcOnlyForType = -1;
    l = LyricFix.fetch(null, "0039MnYb0qxYhV", "");
    if (!xml.equals(l.qrc)) { fails++; System.out.println("FAIL retry"); } else System.out.println("ok   retries other type, calls=" + QQMusicApi.calls);
    QQMusicApi.fail = true;
    try { LyricFix.fetch(null, "x", "1"); fails++; System.out.println("FAIL no error"); } catch (Exception e) { System.out.println("ok   error: " + e.getMessage()); }
    System.out.println(fails == 0 ? "ALL PASSED" : fails + " FAILED"); System.exit(fails);
  }
}
