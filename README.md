# render-cache

《Blooming Planet》三渲二试片的渲染中间产物备份（非源码，可随时删除此分支）。

- `frames/`：已渲染的 3D 帧（一拍二，只保留偶数帧，JPEG q97），帧号 = 秒 × 24
- `feat24.npz`：`mv/analyze.py "Blooming Planet.mp3" feat24.npz 24` 的输出
- `run_render.sh`：续渲命令（4 进程，--threads 1 --samples 5 --step 2）

恢复：把 frames/*.jpg 转回 PNG 放进渲染目录，续渲时已存在的帧会自动跳过。
