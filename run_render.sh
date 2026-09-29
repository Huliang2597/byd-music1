#!/usr/bin/env bash
cd "$(dirname "$0")"
for i in 0 1 2 3; do
  nohup python3 /home/user/byd-music1/mv/blooming/scene.py feat24.npz frames --start 217.0 --end 237.5 \
    --threads 1 --samples 5 --step 2 --part $i/4 > logs/part$i.log 2>&1 &
done
