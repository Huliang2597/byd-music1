#!/usr/bin/env python3
"""把原 APK 中有问题的方法改为调用 com.teamolline.qqlyrics.fix 里的修复实现。

用法: apply_smali.py <apktool 解包目录>
"""
import glob
import os
import sys

LYRICS_CO = "Lcom/teamolline/qqlyrics/data/QQMusicApi$lyrics$2;"
LYRIC_FIX = "Lcom/teamolline/qqlyrics/fix/LyricFix;"
EXPORT_FIX = "Lcom/teamolline/qqlyrics/fix/ExportFix;"
QM_CLIENT = "Lcom/teamolline/qqlyrics/fix/QmClient;"

# 整个方法替换：{类: {方法签名行: 新方法体}}
REPLACE = {
    "com/teamolline/qqlyrics/data/QQMusicApi$lyrics$2.smali": {
        ".method public final invokeSuspend(Ljava/lang/Object;)Ljava/lang/Object;": f"""
    .locals 4

    invoke-static {{}}, Lkotlin/coroutines/intrinsics/IntrinsicsKt;->getCOROUTINE_SUSPENDED()Ljava/lang/Object;

    iget v0, p0, {LYRICS_CO}->label:I

    if-eqz v0, :run

    new-instance p1, Ljava/lang/IllegalStateException;

    const-string v0, "call to 'resume' before 'invoke' with coroutine"

    invoke-direct {{p1, v0}}, Ljava/lang/IllegalStateException;-><init>(Ljava/lang/String;)V

    throw p1

    :run
    invoke-static {{p1}}, Lkotlin/ResultKt;->throwOnFailure(Ljava/lang/Object;)V

    iget-object v0, p0, {LYRICS_CO}->this$0:Lcom/teamolline/qqlyrics/data/QQMusicApi;

    iget-object v1, p0, {LYRICS_CO}->$mid:Ljava/lang/String;

    iget-object v2, p0, {LYRICS_CO}->$id:Ljava/lang/String;

    invoke-static {{v0, v1, v2}}, {LYRIC_FIX}->fetch(Lcom/teamolline/qqlyrics/data/QQMusicApi;Ljava/lang/String;Ljava/lang/String;)Lcom/teamolline/qqlyrics/model/Lyrics;

    move-result-object v0

    return-object v0
""",
    },
    "com/teamolline/qqlyrics/data/QQMusicApi.smali": {
        ".method private final officialRequest(Ljava/lang/String;Ljava/lang/String;Lorg/json/JSONObject;)Lorg/json/JSONObject;": f"""
    .locals 1

    invoke-static {{p1, p2, p3}}, {QM_CLIENT}->request(Ljava/lang/String;Ljava/lang/String;Lorg/json/JSONObject;)Lorg/json/JSONObject;

    move-result-object v0

    return-object v0
""",
    },
    "com/teamolline/qqlyrics/model/LyricsExport.smali": {
        ".method private final formatTime(J)Ljava/lang/String;": f"""
    .locals 1

    invoke-static {{p1, p2}}, {LYRIC_FIX}->formatTime(J)Ljava/lang/String;

    move-result-object v0

    return-object v0
""",
        ".method public final qrcToLrc(Ljava/lang/String;)Ljava/lang/String;": f"""
    .locals 1

    invoke-static {{p1}}, {LYRIC_FIX}->qrcToLrc(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v0

    return-object v0
""",
        ".method public final readableTrack(Ljava/lang/String;)Ljava/lang/String;": f"""
    .locals 1

    invoke-static {{p1}}, {LYRIC_FIX}->readableTrack(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v0

    return-object v0
""",
    },
    "com/teamolline/qqlyrics/MainActivityKt.smali": {
        ".method private static final correctDocumentName(Landroid/content/Context;Landroid/net/Uri;Lcom/teamolline/qqlyrics/PendingExport;)Landroid/net/Uri;": f"""
    .locals 1

    invoke-static {{p0, p1, p2}}, {EXPORT_FIX}->correctDocumentName(Landroid/content/Context;Landroid/net/Uri;Lcom/teamolline/qqlyrics/PendingExport;)Landroid/net/Uri;

    move-result-object v0

    return-object v0
""",
    },
}

# 在方法第一条指令前插入：{类: {方法签名行: 插入的指令}}
PREPEND = {
    "com/teamolline/qqlyrics/MainActivityKt.smali": {
        ".method private static final QQLyricsApp$export(Landroidx/activity/compose/ManagedActivityResultLauncher;Landroidx/compose/runtime/MutableState;Landroidx/compose/runtime/MutableState;Ljava/lang/String;Ljava/lang/String;)V": f"""
    invoke-static {{p3, p4}}, {LYRIC_FIX}->prepareExport(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;

    move-result-object p4
""",
    },
}


def find_smali(root, rel):
    hits = glob.glob(os.path.join(root, "smali*", rel))
    if len(hits) != 1:
        sys.exit(f"找不到或找到多个 {rel}: {hits}")
    return hits[0]


def method_span(lines, header):
    start = next((i for i, l in enumerate(lines) if l.rstrip("\n") == header), None)
    if start is None:
        sys.exit(f"找不到方法: {header}")
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == ".end method")
    return start, end


def is_instruction(line):
    s = line.strip()
    return bool(s) and not s.startswith((".", ":", "#", '"', "}")) and not s.endswith(",") and s[0].isalpha()


def main(root):
    for rel in sorted(set(REPLACE) | set(PREPEND)):
        path = find_smali(root, rel)
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        for header, body in REPLACE.get(rel, {}).items():
            start, end = method_span(lines, header)
            lines[start:end + 1] = [header + "\n"] + [l + "\n" for l in body.strip("\n").split("\n")] + [".end method\n"]
            print(f"替换 {rel} :: {header.split('(')[0].split()[-1]}")
        for header, code in PREPEND.get(rel, {}).items():
            start, end = method_span(lines, header)
            in_annotation = False
            for i in range(start + 1, end):
                s = lines[i].strip()
                if s.startswith(".annotation"):
                    in_annotation = True
                elif s == ".end annotation":
                    in_annotation = False
                elif not in_annotation and (is_instruction(lines[i]) or s.startswith(".line")):
                    lines[i:i] = ["\n"] + [l + "\n" for l in code.strip("\n").split("\n")] + ["\n"]
                    break
            else:
                sys.exit(f"找不到插入点: {header}")
            print(f"插入 {rel} :: {header.split('(')[0].split()[-1]}")
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
