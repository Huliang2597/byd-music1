"""模拟 u.y.qq.com/cgi-bin/musicu.fcg，记录收到的请求。"""
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

LYRIC_HEX = open(sys.argv[2]).read().strip()
LOG = open(sys.argv[3], "w")

def ok(data):
    return {"code": 0, "request": {"code": 0, "data": data}}

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        LOG.write(json.dumps({"headers": {k: self.headers[k] for k in ("Cookie", "User-Agent")}, "body": body}, ensure_ascii=False) + "\n"); LOG.flush()
        req = body["request"]; m = req["method"]; comm = body["comm"]
        if m == "GetSession":
            resp = ok({"session": {"uid": "u1", "sid": "s1", "userip": "1.2.3.4"}})
        elif comm.get("sid") != "s1" or comm.get("tmeAppID") != "qqmusiclight":
            resp = {"code": 0, "request": {"code": 2001, "data": {}}}
        elif m == "DoSearchForQQMusicLite":
            resp = ok({"meta": {"sum": 1}, "body": {"item_song": [{"id": 123, "mid": "M1", "title": "晴天", "singer": [{"name": "周杰伦"}, {"name": "B"}], "album": {"name": "叶惠美"}, "interval": 269}]}})
        elif m == "GetPlayLyricInfo":
            p = req["param"]
            if p.get("crypt") == 1:
                resp = ok({"songID": p["songID"], "lyric": LYRIC_HEX, "trans": "", "roma": "", "qrc_t": 1, "lrc_t": 1})
            else:
                resp = ok({"songID": p["songID"], "lyric": "", "trans": "", "roma": ""})
        elif m == "get_song_detail_yqq":
            resp = ok({"track_info": {"id": 456, "mid": "M2", "title": "七里香", "singer": [{"name": "周杰伦"}], "album": {"name": "七里香"}, "interval": 299}})
        else:
            resp = {"code": 0, "request": {"code": 500001, "data": {}}}
        out = json.dumps(resp, ensure_ascii=False).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)
    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
