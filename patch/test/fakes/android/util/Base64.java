package android.util;
public class Base64 { public static final int DEFAULT = 0; public static final int NO_WRAP = 2;
  public static byte[] decode(String s, int f) { return java.util.Base64.getMimeDecoder().decode(s); }
  public static String encodeToString(byte[] b, int f) { return java.util.Base64.getEncoder().encodeToString(b); } }
