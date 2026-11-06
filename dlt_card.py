#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""超级大乐透号码生成 + 表格样式卡片渲染（跨平台，可在 GitHub Actions 运行）。

号码生成：基于历史开奖数据的极大似然估计(MLE)分布加权、无放回抽样。
          - 前区权重 p_i = 号码 i 出现期数 / 总期数（理论均值 5/35）
          - 后区权重 q_j = 号码 j 出现期数 / 总期数（理论均值 2/12）
          - 同一注内号码不重复；不与历史已开出的组合重复；多注之间不重复
          - 历史数据每次运行自动增量更新（随开奖滚动刷新）
          - 网络不可用时自动降级为等概率机选，不影响出图

图片样式：白色圆角表格卡片，左列「前区」5 个号码，右列「后区」2 个号码。

用法：python dlt_card.py [注数=5] [输出路径]
字体：可用环境变量 DLT_FONT_BD / DLT_FONT_RG 指定，未指定时自动探测系统中文字体。
"""
import datetime
import glob
import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

import dlt_data

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(HERE, "state")
DEFAULT_OUT = os.path.join(STATE_DIR, "latest.png")

# 参考样式配色
BG_OUT = (240, 241, 243)      # 画布浅灰
CARD = (255, 255, 255)        # 卡片白
HEADER_BG = (245, 246, 247)   # 表头浅灰
INK = (52, 57, 64)            # 号码深灰
LINE = (227, 230, 234)        # 分隔线

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

_FONT_CACHE = {}


def _font_candidates(bold):
    """按平台优先级给出候选字体 (路径, ttc 索引)。"""
    key = "BD" if bold else "RG"
    env = os.environ.get("DLT_FONT_" + key)
    cands = []
    if env:
        cands.append((env, 0))
    if bold:
        cands += [
            ("C:/Windows/Fonts/msyhbd.ttc", 0),           # 微软雅黑 Bold
            ("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf", 0),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 2),  # SC 在 2 号位
            ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 2),
            ("/usr/share/fonts/truetype/noto/NotoSansSC-Bold.otf", 0),
            ("/System/Library/Fonts/PingFang.ttc", 1),
        ]
    else:
        cands += [
            ("C:/Windows/Fonts/msyh.ttc", 0),
            ("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf", 0),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2),
            ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 2),
            ("/System/Library/Fonts/PingFang.ttc", 1),
        ]
    return cands


def _resolve_font(bold):
    key = "BD" if bold else "RG"
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    for path, index in _font_candidates(bold):
        if path and os.path.exists(path):
            _FONT_CACHE[key] = (path, index)
            return _FONT_CACHE[key]
    # 兜底：在常见字体目录里找任何 Noto CJK 字体
    for pattern in ("/usr/share/fonts/**/*CJK*Bold*", "/usr/share/fonts/**/*CJK*"):
        for hit in sorted(glob.glob(pattern, recursive=True)):
            if hit.lower().endswith((".ttc", ".otf", ".ttf")):
                _FONT_CACHE[key] = (hit, 0 if hit.lower().endswith((".otf", ".ttf")) else 2)
                return _FONT_CACHE[key]
    _FONT_CACHE[key] = (None, 0)
    return _FONT_CACHE[key]


def font(size, bold=True):
    path, index = _resolve_font(bold)
    if not path:
        print("[警告] 未找到可用中文字体，回退到默认字体（中文可能显示为方块）")
        return ImageFont.load_default()
    for idx in (index, 0):
        try:
            return ImageFont.truetype(path, size, index=idx)
        except Exception:
            continue
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def weighted_sample(weights, k):
    """无放回加权抽样，weights[i] 对应号码 i+1。返回升序号码列表。"""
    idx = list(range(len(weights)))
    picked = []
    for _ in range(min(k, len(idx))):
        total = math.fsum(weights[i] for i in idx)
        r = random.random() * total
        chosen = idx[-1]
        acc = 0.0
        for pos, i in enumerate(idx):
            acc += weights[i]
            if acc >= r:
                chosen = i
                idx.pop(pos)
                break
        picked.append(chosen + 1)
    return sorted(picked)


def load_model():
    """返回 (front_w, back_w, 历史组合集合, 说明文字)。数据源不可用时降级等概率。"""
    try:
        draws, _ = dlt_data.update(verbose=True)
        if len(draws) < 100:
            raise RuntimeError("历史数据不足（%d 期）" % len(draws))
        fw, bw, n = dlt_data.mle_weights(draws)
        return fw, bw, dlt_data.history_combos(draws), "MLE 加权机选 · 基于近 %d 期开奖统计" % n
    except Exception as e:
        print("[警告] 历史数据不可用（%s），降级为等概率机选" % e)
        return ([1.0 / 35] * 35, [1.0 / 12] * 12, set(), "等概率机选 · 理性购彩")


def gen_tickets(n, front_w, back_w, history):
    """生成 n 注：排除与历史开奖相同的组合，且各注之间不重复。"""
    tickets, seen = [], set()
    for _ in range(n * 400):
        if len(tickets) >= n:
            break
        combo = (tuple(weighted_sample(front_w, 5)), tuple(weighted_sample(back_w, 2)))
        if combo in history or combo in seen:
            continue
        seen.add(combo)
        tickets.append([list(combo[0]), list(combo[1])])
    return tickets


def render(tickets, out_path):
    """按参考样式渲染：浅灰画布上的白色圆角表格卡片（2 倍超采样抗锯齿）。

    列宽：前区固定 400px，后区按号码文本宽度自适应。
    """
    s = 2
    margin_x, margin_y, radius = 20, 12, 20
    header_h, row_h = 76, 84
    col_pad = 25               # 每列左右内边距
    front_col_w = 400          # 前区列宽（固定值）
    n = len(tickets)

    f_head = font(52, bold=True)
    f_num = font(54, bold=True)

    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    front_txt = max(" ".join("%02d" % v for v in f) for f, _ in tickets)
    back_txt = max(" ".join("%02d" % v for v in b) for _, b in tickets)
    front_txt_w = int(probe.textlength(front_txt, font=f_num))
    col_front = front_col_w
    if front_txt_w + 10 > col_front:   # 内容放不下时自动放宽，避免文字压线/裁切
        col_front = front_txt_w + 10
        print("[提示] 前区号码较宽，列宽自动放宽至 %dpx" % col_front)
    col_back = max(int(probe.textlength(back_txt, font=f_num)) + col_pad * 2, 200)

    card_l, card_t = margin_x, margin_y
    card_r = card_l + col_front + col_back
    card_b = card_t + header_h + n * row_h
    col_split = card_l + col_front
    width, height = card_r + margin_x, card_b + margin_y

    img = Image.new("RGB", (width * s, height * s), BG_OUT)
    d = ImageDraw.Draw(img)

    # 白色圆角卡片
    d.rounded_rectangle([card_l * s, card_t * s, card_r * s, card_b * s],
                        radius=radius * s, fill=CARD)
    # 表头浅灰底（顶部圆角、底部直角）
    d.rounded_rectangle([card_l * s, card_t * s, card_r * s, (card_t + header_h) * s],
                        radius=radius * s, fill=HEADER_BG)
    d.rectangle([card_l * s, (card_t + header_h // 2) * s,
                 card_r * s, (card_t + header_h) * s], fill=HEADER_BG)

    # 表头文字
    hy = (card_t + header_h / 2.0) * s
    d.text(((card_l + col_split) / 2.0 * s, hy), "前区",
           font=f_head, fill=INK, anchor="mm")
    d.text(((col_split + card_r) / 2.0 * s, hy), "后区",
           font=f_head, fill=INK, anchor="mm")

    # 分隔线
    lw = 1 * s
    y = (card_t + header_h) * s
    d.line([card_l * s, y, card_r * s, y], fill=LINE, width=lw)
    for i in range(1, n):
        y = (card_t + header_h + i * row_h) * s
        d.line([card_l * s, y, card_r * s, y], fill=LINE, width=lw)
    x = col_split * s
    d.line([x, card_t * s, x, card_b * s], fill=LINE, width=lw)

    # 号码文本
    for i, (front, back) in enumerate(tickets):
        cy = (card_t + header_h + (i + 0.5) * row_h) * s
        d.text((col_split / 2.0 * s, cy), " ".join("%02d" % v for v in front),
               font=f_num, fill=INK, anchor="mm")
        d.text(((col_split + card_r) / 2.0 * s, cy), " ".join("%02d" % v for v in back),
               font=f_num, fill=INK, anchor="mm")

    img = img.resize((width, height), Image.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def main():
    n = 5
    if len(sys.argv) > 1:
        try:
            n = max(1, min(10, int(sys.argv[1])))
        except ValueError:
            pass
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT

    front_w, back_w, history, note = load_model()
    tickets = gen_tickets(n, front_w, back_w, history)
    if len(tickets) < n:
        print("[警告] 去重后仅生成 %d 注" % len(tickets))
    render(tickets, out)

    # 供推送脚本做文字兜底（图片加载失败时也能看到号码）
    meta_path = os.path.join(os.path.dirname(os.path.abspath(out)), "tickets.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "note": note,
            "tickets": [{"front": front, "back": back} for front, back in tickets],
        }, f, ensure_ascii=False, indent=2)

    for i, (front, back) in enumerate(tickets, 1):
        print("第%d注: %s + %s" % (i,
                                   " ".join("%02d" % x for x in front),
                                   " ".join("%02d" % x for x in back)))
    print("依据: %s" % note)
    print("图片路径: %s" % os.path.abspath(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
