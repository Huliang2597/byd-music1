"""模拟 QQ 音乐接口（u.y.qq.com 与 c.y.qq.com），记录收到的请求。

用法: server.py <端口> <qrc.hex> <log.jsonl> <模式>
模式 lite_ok：简洁版接口正常；lite_2001：u.y.qq.com/musicu.fcg 一律返回 2001；
all_fail：所有接口都失败。
"""
import base64, json, re, sys
from hashlib import sha1
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

PORT, HEX, LOG, MODE = int(sys.argv[1]), open(sys.argv[2]).read().strip(), open(sys.argv[3], "w"), sys.argv[4]
SONG = {"id": 123, "mid": "M1", "title": "晴天", "name": "晴天", "singer": [{"name": "周杰伦"}, {"name": "B"}], "album": {"name": "叶惠美"}, "interval": 269}

def zzc_sign(payload):  # 与 QQMusicApi 的 qqmusic_api/algorithms/sign.py 相同
    h = sha1(payload).hexdigest().upper()
    p1 = "".join(h[i] for i in [23, 14, 6, 36, 16, 7, 19]); p2 = "".join(h[i] for i in [16, 1, 32, 12, 19, 27, 8, 5])
    sc = [89, 39, 179, 150, 218, 82, 58, 252, 177, 52, 186, 123, 120, 64, 242, 133, 143, 161, 121, 179]
    p3 = bytes(v ^ int(h[i * 2:i * 2 + 2], 16) for i, v in enumerate(sc))
    return ("zzc" + p1 + re.sub(rb"[\\/+=]", b"", base64.b64encode(p3)).decode() + p2).lower()

def ok(key, data):
    return {"code": 0, key: {"code": 0, "data": data}}

class H(BaseHTTPRequestHandler):
    def reply(self, obj, raw=None):
        out = raw.encode() if raw is not None else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)

    def log(self, body):
        u = urlparse(self.path)
        LOG.write(json.dumps({"path": u.path, "query": parse_qs(u.query), "headers": {k: self.headers[k] for k in ("Cookie", "User-Agent", "Referer") if self.headers[k]}, "body": body}, ensure_ascii=False) + "\n"); LOG.flush()

    def do_GET(self):
        self.log(None)
        u = urlparse(self.path); q = parse_qs(u.query)
        if MODE == "all_fail":
            return self.reply({"code": 500})
        if u.path.endswith("client_search_cp"):
            return self.reply({"code": 0, "data": {"song": {"list": [SONG]}}})
        if u.path.endswith("smartbox_new.fcg"):
            return self.reply({"code": 0, "data": {"song": {"itemlist": [{"id": "123", "mid": "M1", "name": "晴天", "singer": "周杰伦"}]}}})
        if u.path.endswith("fcg_play_single_song.fcg"):
            mid = q.get("songmid", [""])[0]
            return self.reply({"code": 0, "data": [{"id": 456, "mid": mid, "title": "七里香", "singer": [{"name": "周杰伦"}], "album": {"name": "七里香"}, "interval": 299}]})
        if u.path.endswith("fcg_query_lyric_new.fcg"):
            return self.reply(None, 'MusicJsonCallback({"retcode":0,"code":0,"lyric":"' + base64.b64encode("[00:01.00]故事的小\n".encode()).decode() + '","trans":""})')
        self.reply({"code": 404})

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path.endswith("lyric_download.fcg"):
            self.log(raw.decode())
            if MODE == "all_fail":
                return self.reply({"code": 500})
            return self.reply(None, '<?xml version="1.0" encoding="utf-8"?>\n<!--<lyric><content>' + HEX + '</content><contentts></contentts><contentroma></contentroma></lyric>-->')
        body = json.loads(raw)
        self.log(body)
        if u.path.endswith("musics.fcg"):
            if MODE == "all_fail":
                return self.reply({"code": 2001})
            if q.get("sign", [""])[0] != zzc_sign(raw):
                return self.reply({"code": 0, "req_1": {"code": 2001, "data": {}}})
            return self.reply(ok("req_1", {"body": {"song": {"list": [SONG]}}}))
        # musicu.fcg（简洁版）
        if MODE != "lite_ok":
            return self.reply({"code": 0, "request": {"code": 2001, "data": {}}})
        req = body["request"]; m = req["method"]; comm = body["comm"]
        if m == "GetSession":
            return self.reply(ok("request", {"session": {"uid": "u1", "sid": "s1", "userip": "1.2.3.4"}}))
        if comm.get("sid") != "s1" or comm.get("tmeAppID") != "qqmusiclight":
            return self.reply({"code": 0, "request": {"code": 2001, "data": {}}})
        if m == "DoSearchForQQMusicLite":
            return self.reply(ok("request", {"meta": {"sum": 1}, "body": {"item_song": [SONG]}}))
        if m == "GetPlayLyricInfo":
            p = req["param"]
            if p.get("crypt") == 1:
                return self.reply(ok("request", {"songID": p["songID"], "lyric": HEX, "trans": "", "roma": ""}))
            return self.reply(ok("request", {"songID": p["songID"], "lyric": "", "trans": "", "roma": ""}))
        if m == "get_song_detail_yqq":
            return self.reply(ok("request", {"track_info": {"id": 456, "mid": req["param"].get("song_mid", "M2"), "title": "七里香", "singer": [{"name": "周杰伦"}], "album": {"name": "七里香"}, "interval": 299}}))
        self.reply({"code": 0, "request": {"code": 500001, "data": {}}})

    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", PORT), H).serve_forever()
