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

echo "==> 重新打包"
java -jar "$TOOLS/apktool.jar" b "$WORK/apk" -o "$WORK/unsigned.apk"
python3 - "$WORK/unsigned.apk" "$WORK/fix.dex" <<'EOF'
import sys, zipfile
apk, dex = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(apk) as z:
    names = set(z.namelist())
n = 2
while f"classes{n}.dex" in names:
    n += 1
with zipfile.ZipFile(apk, "a", zipfile.ZIP_DEFLATED) as z:
    z.write(dex, f"classes{n}.dex")
print(f"已加入 classes{n}.dex")
EOF

echo "==> 对齐并签名"
rm -rf "$WORK/signed"
java -jar "$TOOLS/uber-apk-signer.jar" -a "$WORK/unsigned.apk" -o "$WORK/signed" --allowResign
cp "$WORK"/signed/*.apk "$OUT_APK"
echo "==> 完成: $OUT_APK"
