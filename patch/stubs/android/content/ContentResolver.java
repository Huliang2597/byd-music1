package android.content;
import android.database.Cursor; import android.net.Uri;
public abstract class ContentResolver {
  public final Cursor query(Uri u, String[] p, String s, String[] a, String o) { throw new RuntimeException("stub"); }
  public final Uri insert(Uri u, ContentValues v) { throw new RuntimeException("stub"); }
  public final int delete(Uri u, String w, String[] a) { throw new RuntimeException("stub"); }
}
