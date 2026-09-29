package android.util;
public class Base64 { public static final int DEFAULT = 0;
  public static byte[] decode(String s, int f) { return java.util.Base64.getMimeDecoder().decode(s); } }
