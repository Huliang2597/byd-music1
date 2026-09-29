package io.github.proify.qrckit.decrypt;
/** Test double: same algorithm as the app (3DES from the APK's DESHelper + zlib). */
public final class QrcDecrypter {
  public static final QrcDecrypter INSTANCE = new QrcDecrypter();
  public final String decrypt(String hex) {
    try {
      byte[] e = new byte[hex.length() / 2];
      for (int i = 0; i < e.length; i++) e[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
      byte[][][] s = new byte[3][16][6];
      DESHelper.INSTANCE.tripleDESKeySetup("!@#)(*$%123ZXC!@!@#)(NHL".getBytes("US-ASCII"), s, 0);
      byte[] d = new byte[e.length], in = new byte[8], t = new byte[8];
      for (int i = 0; i < e.length; i += 8) { System.arraycopy(e, i, in, 0, 8); DESHelper.INSTANCE.tripleDESCrypt(in, t, s); System.arraycopy(t, 0, d, i, 8); }
      java.io.InputStream z = new java.util.zip.InflaterInputStream(new java.io.ByteArrayInputStream(d));
      java.io.ByteArrayOutputStream o = new java.io.ByteArrayOutputStream(); byte[] b = new byte[4096]; int n;
      while ((n = z.read(b)) > 0) o.write(b, 0, n);
      return new String(o.toByteArray(), "UTF-8");
    } catch (Exception ex) { return null; }
  }
}
