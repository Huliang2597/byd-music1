#!/usr/bin/env bash
# 在 JVM 上跑修复类的单元测试。
# 用法: patch/test/run.sh <原版.apk>
# 3DES 使用 APK 自带的 DESHelper（经 dex2jar 转换），所以需要原版 APK。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PATCH="$(dirname "$HERE")"
APK="$(realpath "${1:?用法: run.sh <原版.apk>}")"
TOOLS="$PATCH/tools"
WORK="$PATCH/work/test"
DEX2JAR_URL="https://github.com/pxb1988/dex2jar/releases/download/v2.4/dex-tools-v2.4.zip"

if [ ! -d "$TOOLS/dex-tools" ]; then
  mkdir -p "$TOOLS"
  curl -fsSL -o "$TOOLS/dex-tools.zip" "$DEX2JAR_URL"
  unzip -q -o "$TOOLS/dex-tools.zip" -d "$TOOLS/dex-tools"
  rm -f "$TOOLS/dex-tools.zip"
fi
D2J="$(ls -d "$TOOLS"/dex-tools/*/)"

rm -rf "$WORK"; mkdir -p "$WORK/dex" "$WORK/jars" "$WORK/a" "$WORK/b"
unzip -q -o "$APK" 'classes*.dex' -d "$WORK/dex"
for dex in "$WORK"/dex/*.dex; do
  sh "$D2J/d2j-dex2jar.sh" -f -o "$WORK/jars/$(basename "$dex" .dex).jar" "$dex" >/dev/null 2>&1
done
# classes3 里是 app 的 UI 代码，测试用不到，且会与测试替身冲突
CP="$(ls "$WORK"/jars/*.jar | grep -v '/classes3.jar' | tr '\n' ':')"
# dex2jar 生成的字节码缺少 StackMapTable，需要关闭校验
JVM=(java -XX:+UnlockDiagnosticVMOptions -XX:-BytecodeVerificationRemote -XX:-BytecodeVerificationLocal)

# 1) 纯函数测试：真实 3DES + java.util.Base64 替身
javac -nowarn -encoding UTF-8 -d "$WORK/a/stubs" $(find "$PATCH/stubs" -name '*.java' | grep -v 'android/util/Base64\|QrcDecrypter')
javac -nowarn -encoding UTF-8 -cp "$WORK/a/stubs:$CP" -d "$WORK/a/cls" \
  "$HERE/fakes/android/util/Base64.java" "$HERE/fakes/io/github/proify/qrckit/decrypt/QrcDecrypter.java" \
  $(find "$PATCH/src" -name '*.java') "$HERE/LyricFixTest.java"
"${JVM[@]}" -cp "$WORK/a/cls:$WORK/a/stubs:$CP" LyricFixTest "$HERE/fixtures/qrc.xml" "$HERE/fixtures/qrc.hex"

# 2) 获取流程测试：假的 QQMusicApi（返回 QRC 但不带 "qrc" 标志）
javac -nowarn -encoding UTF-8 -cp "$CP" -d "$WORK/b" $(find "$HERE/fakes" -name '*.java') \
  "$PATCH/src/com/teamolline/qqlyrics/fix/LyricFix.java" "$HERE/FetchTest.java"
"${JVM[@]}" -cp "$WORK/b:$CP" FetchTest "$HERE/fixtures/qrc.xml" "$HERE/fixtures/qrc.hex"
