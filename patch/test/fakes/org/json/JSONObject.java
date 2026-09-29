package org.json;
import java.util.*;
public class JSONObject {
  public final Map<String, Object> m = new LinkedHashMap<>();
  public JSONObject() { }
  public JSONObject put(String k, Object v) { m.put(k, v); return this; }
  public JSONObject put(String k, int v) { m.put(k, v); return this; }
  public JSONObject put(String k, long v) { m.put(k, v); return this; }
  public JSONObject optJSONObject(String k) { Object o = m.get(k); return o instanceof JSONObject ? (JSONObject) o : null; }
  public String optString(String k) { Object o = m.get(k); return o == null ? "" : o.toString(); }
  public String toString() { return m.toString(); }
}
