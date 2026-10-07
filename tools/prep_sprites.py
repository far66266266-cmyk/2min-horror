# 生成した人物画像（work/sprite_cand/*.png）をゲーム用の切り抜き img/*.webp にする
#   python tools/prep_sprites.py
# 透過 PNG ならそのまま、純緑背景なら緑を抜く。余白を詰め、足元が画像の下端に来るようにして高さ512pxに縮める
import os, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'sprite_cand')
DST = os.path.join(ROOT, 'img')
NAMES = ['fig_stand', 'fig_tilt', 'fig_lean', 'guard_a', 'guard_b', 'guard_c', 'guard_d',
         'obj_chair', 'obj_wheelchair', 'obj_doll', 'obj_umbrella', 'obj_randoseru', 'obj_balloon', 'obj_box',
         'fig_walk1', 'fig_walk2', 'fig_man', 'fig_oldwoman', 'fig_child', 'fig_crawl']


def key_green(rgb):
    r, g, b = [rgb[..., i].astype(np.float32) for i in range(3)]
    greenness = g - np.maximum(r, b)                  # 緑だけが強いほど背景
    alpha = np.clip(1 - (greenness - 25) / 70, 0, 1)  # 25以下は人物、95以上は背景、間はなめらかに
    # 縁に残る緑かぶりを抑える
    g2 = np.minimum(g, np.maximum(r, b) + 8)
    out = np.stack([r, g2, b], -1)
    return out.astype(np.uint8), (alpha * 255).astype(np.uint8)


def main():
    os.makedirs(DST, exist_ok=True)
    for n in NAMES:
        path = os.path.join(SRC, n + '.png')
        if not os.path.exists(path):
            print(f'{n}: なし'); continue
        im = Image.open(path).convert('RGBA')
        a = np.array(im)
        mode = '透過'
        if a[..., 3].min() == 255:                    # アルファが無い → 緑を抜く
            rgb, alpha = key_green(a[..., :3]); a = np.dstack([rgb, alpha]); mode = '緑抜き'
        al = a[..., 3]
        ys, xs = np.where(al > 24)
        if len(ys) == 0:
            print(f'{n}: 人物が見つからない'); continue
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        out = Image.fromarray(a[y0:y1, x0:x1], 'RGBA')
        h = 512; w = max(1, round(out.width * h / out.height))
        out = out.resize((w, h), Image.LANCZOS)
        dst = os.path.join(DST, n + '.webp')
        out.save(dst, 'WEBP', quality=86, method=6)
        print(f'{n}: {mode}  {out.width}x{out.height}  {os.path.getsize(dst)//1024}KB')


if __name__ == '__main__':
    main()
