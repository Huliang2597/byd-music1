#!/usr/bin/env python3
"""以原版 APK 为底，只替换改动过的 dex 并加入修复类 dex。

用法: assemble.py <原版.apk> <apktool 重建的.apk> <fix.dex> <输出.apk>
"""
import sys
import zipfile

CHANGED = {"classes3.dex", "classes5.dex", "classes6.dex"}


def dex_version(data):
    return data[4:7].decode("ascii")


def main(src, rebuilt, fix_dex, out):
    with zipfile.ZipFile(rebuilt) as rz:
        replaced = {name: rz.read(name) for name in CHANGED}
    for name, data in replaced.items():
        if dex_version(data) != "037":
            sys.exit(f"{name} 的 dex 版本是 {dex_version(data)}，应为 037")
    with open(fix_dex, "rb") as f:
        fix = f.read()

    with zipfile.ZipFile(src) as sz, zipfile.ZipFile(out, "w") as oz:
        names = set(sz.namelist())
        for info in sz.infolist():
            upper = info.filename.upper()
            if upper.startswith("META-INF/") and upper.endswith((".SF", ".RSA", ".DSA", ".EC", "MANIFEST.MF")):
                continue  # 旧签名
            data = replaced.get(info.filename)
            if data is None:
                data = sz.read(info.filename)
            new = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            new.compress_type = info.compress_type
            new.external_attr = info.external_attr
            oz.writestr(new, data)
        n = 2
        while f"classes{n}.dex" in names:
            n += 1
        new = zipfile.ZipInfo(f"classes{n}.dex", date_time=(1981, 1, 1, 1, 1, 0))
        new.compress_type = zipfile.ZIP_DEFLATED
        oz.writestr(new, fix)
        print(f"替换 {sorted(CHANGED)}，加入 classes{n}.dex")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
