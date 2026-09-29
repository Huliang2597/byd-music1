#!/usr/bin/env bash
# 用原版 “QQ 歌词” 1.0.1 APK 生成修复版 APK。
#
# 用法: patch/build.sh <原版.apk> [输出.apk]
# 依赖: JDK 11+、python3、curl、unzip（工具 jar 会自动下载到 patch/tools/）
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC_APK="$(realpath "${1:?用法: build.sh <原版.apk> [输出.apk]}")"
OUT_APK="$(realpath -m "${2:-$HERE/out/QQLyrics-1.0.1-fix.apk}")"
TOOLS="$HERE/tools"
WORK="$HERE/work"

APKTOOL_URL="https://github.com/iBotPeaches/Apktool/releases/download/v2.10.0/apktool_2.10.0.jar"
DEX2JAR_URL="https://github.com/pxb1988/dex2jar/releases/download/v2.4/dex-tools-v2.4.zip"
SIGNER_URL="https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar"

mkdir -p "$TOOLS"
[ -f "$TOOLS/apktool.jar" ] || curl -fsSL -o "$TOOLS/apktool.jar" "$APKTOOL_URL"
[ -f "$TOOLS/uber-apk-signer.jar" ] || curl -fsSL -o "$TOOLS/uber-apk-signer.jar" "$SIGNER_URL"
if [ ! -f "$TOOLS/dx.jar" ]; then
  curl -fsSL -o "$TOOLS/dex-tools.zip" "$DEX2JAR_URL"
  unzip -q -o -j "$TOOLS/dex-tools.zip" '*/lib/dx-*.jar' -d "$TOOLS"
  mv "$TOOLS"/dx-*.jar "$TOOLS/dx.jar"
  rm -f "$TOOLS/dex-tools.zip"
fi

rm -rf "$WORK"
mkdir -p "$WORK/stubs" "$WORK/classes" "$(dirname "$OUT_APK")"

echo "==> 解包"
java -jar "$TOOLS/apktool.jar" d -f -r -o "$WORK/apk" "$SRC_APK"

echo "==> 修改 smali"
python3 "$HERE/apply_smali.py" "$WORK/apk"

echo "==> 编译修复类"
javac --release 8 -nowarn -encoding UTF-8 -d "$WORK/stubs" $(find "$HERE/stubs" -name '*.java')
javac --release 8 -nowarn -encoding UTF-8 -cp "$WORK/stubs" -d "$WORK/classes" $(find "$HERE/src" -name '*.java')
java -cp "$TOOLS/dx.jar" com.android.dx.command.Main --dex --min-sdk-version=24 \
  --output="$WORK/fix.dex" "$WORK/classes"

echo "==> 重新汇编改动过的 dex"
# apktool 在 apktool.yml 缺少 sdkInfo 时会按 API 15 生成 dex 035，
# 而原 App 的 Kotlin/Compose 代码需要 dex 037（API 24），否则启动即闪退。
python3 - "$WORK/apk/apktool.yml" <<'EOF'
import re, sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
s = re.sub(r"^sdkInfo:.*$", "sdkInfo:\n  minSdkVersion: 24\n  targetSdkVersion: 35", s, count=1, flags=re.M)
open(p, "w", encoding="utf-8").write(s)
EOF
java -jar "$TOOLS/apktool.jar" b "$WORK/apk" -o "$WORK/rebuilt.apk"

echo "==> 组装 APK（除改动的 dex 外，其余文件与原版逐字节相同）"
python3 "$HERE/assemble.py" "$SRC_APK" "$WORK/rebuilt.apk" "$WORK/fix.dex" "$WORK/unsigned.apk"

echo "==> 对齐并签名"
KS="$TOOLS/qqlyrics-fix.jks"
if [ ! -f "$KS" ]; then
  keytool -genkeypair -keystore "$KS" -storetype JKS -alias qqlyrics -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass qqlyrics -keypass qqlyrics -dname "CN=QQLyrics Fix, O=QQLyrics, C=CN"
fi
rm -rf "$WORK/signed"
java -jar "$TOOLS/uber-apk-signer.jar" -a "$WORK/unsigned.apk" -o "$WORK/signed" \
  --ks "$KS" --ksAlias qqlyrics --ksPass qqlyrics --ksKeyPass qqlyrics
cp "$WORK"/signed/*.apk "$OUT_APK"
echo "==> 完成: $OUT_APK"
