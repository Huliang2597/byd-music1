import com.teamolline.qqlyrics.fix.LyricFix;
import java.nio.file.*;

public class LyricFixTest {
  static int fails = 0;
  static void eq(String name, Object exp, Object act) {
    if (!String.valueOf(exp).equals(String.valueOf(act))) { fails++; System.out.println("FAIL " + name + "\n  expected: " + exp + "\n  actual:   " + act); }
    else System.out.println("ok   " + name);
  }
  public static void main(String[] a) throws Exception {
    String xml = new String(Files.readAllBytes(Paths.get(a[0])), "UTF-8");
    String hex = new String(Files.readAllBytes(Paths.get(a[1])), "UTF-8").trim();
    String bare = "[ti:晴天]\n[ar:周杰伦]\n[0,1000]故(0,500)事(500,500)\n[61234,1500]Hello (61234,500)world(61734,1000)\n";
    String lrc = "[00:01.00]故事\n[01:01.23]Hello world";

    eq("decode hex -> qrc xml", xml, LyricFix.decodeField(hex));
    eq("decode lowercase hex", xml, LyricFix.decodeField(hex.toLowerCase()));
    eq("decode base64", lrc, LyricFix.decodeField(java.util.Base64.getEncoder().encodeToString(lrc.getBytes("UTF-8"))));
    eq("decode plain", lrc, LyricFix.decodeField(lrc));
    eq("decode garbage", "", LyricFix.decodeField("@@@###"));
    eq("decode null string", "", LyricFix.decodeField("null"));

    eq("isQrc xml", true, LyricFix.isQrc(xml));
    eq("isQrc bare", true, LyricFix.isQrc(bare));
    eq("isQrc lrc", false, LyricFix.isQrc(lrc));
    eq("isQrc empty", false, LyricFix.isQrc(""));

    eq("qrcToLrc bare", "[ti:晴天]\n[ar:周杰伦]\n[00:00.00]故事\n[01:01.23]Hello world", LyricFix.qrcToLrc(bare));
    eq("qrcToLrc xml", "[ti:晴天]\n[ar:周杰伦]\n[00:01.00]故事的小\n[00:03.00]Hello world", LyricFix.qrcToLrc(xml));

    eq("formatTime", "01:01.23", LyricFix.formatTime(61234));
    eq("formatTime round", "00:59.99", LyricFix.formatTime(59994));
    eq("formatTime carry", "01:00.00", LyricFix.formatTime(59996));

    eq("readableTrack drops //", "[00:01.00]a\n[00:03.00]b", LyricFix.readableTrack("[00:01.00]a\n[00:02.00]//\n[00:03.00]b"));
    eq("readableTrack qrc", LyricFix.qrcToLrc(bare), LyricFix.readableTrack(bare));

    eq("prepareExport keeps xml", xml.trim(), LyricFix.prepareExport("qrc", xml));
    String wrapped = LyricFix.prepareExport("qrc", bare);
    eq("prepareExport wraps bare", true, wrapped.startsWith("<?xml") && wrapped.contains("<QrcInfos>") && wrapped.contains("LyricContent=\""));
    eq("wrapped roundtrip", LyricFix.qrcToLrc(bare), LyricFix.qrcToLrc(wrapped));
    eq("prepareExport lrc untouched", lrc, LyricFix.prepareExport("lrc", lrc));
    String special = "[0,500]A&B(0,250)\"x\"(250,250)\n";
    eq("escape roundtrip", "[00:00.00]A&B\"x\"", LyricFix.qrcToLrc(LyricFix.prepareExport("qrc", special)));

    System.out.println(fails == 0 ? "ALL PASSED" : fails + " FAILED");
    System.exit(fails == 0 ? 0 : 1);
  }
}
