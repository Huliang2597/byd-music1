# QQ 歌词 1.0.1 修复补丁

针对 `com.teamolline.qqlyrics` 1.0.1（原 APK 没有源码）做的补丁：解包原 APK，把有问题的方法改为调用 `src/` 里的修复代码，再重新打包、签名。

## 修复的问题

| 现象 | 原因 | 修复 |
| --- | --- | --- |
| 拿不到逐字 QRC，只有普通 LRC | 只有接口返回 `"qrc": 1` 时才解密逐字歌词，但 QQ 音乐并不稳定返回这个字段 | 解密后按内容判断是否为 QRC；拿不到时换 `type` 参数（0 / -1 / 1）重试 |
| 第三方接口的 QRC 是乱码或为空 | 歌词字段只按一种编码处理 | 自动识别 QQ 加密 hex、base64、明文 |
| 裸 QRC 转 LRC 得到空内容 | 只认带 XML 外壳的 QRC | 同时支持 XML 和 `[起始,时长]字(起始,时长)` 格式 |
| 导出的 .qrc 播放器不认逐字 | 导出的内容可能是裸 QRC | 导出 QRC 时补成完整的 QRC XML |
| LRC 时间错乱 | 时间戳写成 `[mm:ss.xxx]`，很多车机/播放器只认 `[mm:ss.xx]` | 改为标准 `[mm:ss.xx]` |
| 合并歌词里出现 `//` 行 | QQ 翻译用 `//` 占位 | 合并时去掉 |
| 保存后文件名是 `xxx.qrc.txt` / `xxx.bin`，只能手动改后缀 | 部分文件选择器会改后缀，并且不支持改名 | 先尝试改名；改不了时（Android 10+）改存到 `下载/QQ歌词/`，并删除改错名的空文件 |

## 构建

需要 JDK 11+、python3、curl、unzip。

```bash
patch/build.sh 原版.apk                 # 输出 patch/out/QQLyrics-1.0.1-fix.apk
patch/test/run.sh 原版.apk              # JVM 单元测试
```

工具（apktool、dx、uber-apk-signer）会自动下载到 `patch/tools/`，签名密钥第一次构建时生成在 `patch/tools/qqlyrics-fix.jks`（不入库）。

打包时只替换改动过的 `classes3/5/6.dex` 并新增修复类的 dex，其余文件与原版逐字节相同（`assemble.py`）。

修复版的签名和原版不同：安装前需要先卸载原版。

## 目录

- `src/`：修复代码（`LyricFix` 负责获取、解码歌词并转换 QRC，`ExportFix` 负责保存文件时的命名）
- `stubs/`：只用于编译的 Android / 原 App 类声明，不会打进 APK
- `apply_smali.py`：修改原 APK 的 smali，让原方法调用修复代码
- `assemble.py`：以原版 APK 为底组装新 APK
- `test/`：单元测试与测试替身
