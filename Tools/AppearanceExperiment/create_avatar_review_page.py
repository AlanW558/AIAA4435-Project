#!/usr/bin/env python3
"""Make a local comparison page from actual Unity review outputs."""
import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checks", required=True, type=Path)
    args = parser.parse_args()
    directory = args.checks.resolve()
    report = json.loads((directory / "checks.json").read_text())
    if not report["passed"]:
        raise SystemExit("Unity checks have not passed.")
    images = {item["image"] for item in report["states"] + report["detailViews"]}
    for name in images:
        if not (directory / name).is_file():
            raise FileNotFoundError(directory / name)
    references = ROOT / "StudyData/avatar-v3/references"
    import os
    def ref(name):
        return html.escape(os.path.relpath(references / name, directory), quote=True)
    pairs = [
        ("蓝西装", "liang-reference-v1.png", "00-liang-suit.png",
         "三维截图为正面；参考图是三分之四视角。"),
        ("运动服", "liang-sport-reference-v1.png", "02-liang-sport.png",
         "Unity 此状态验证红色换色；原参考图的颜色保持原样。"),
        ("裸上身与短裤", "liang-bare-reference-v1.png", "03-liang-none.png",
         "重点检查头身比、颈根和肩部过渡。"),
        ("黄色角色", "nailong-reference-v1.png", "09-nailong-default-front.png",
         "Unity 实际默认状态；整体替换使用此角色。"),
    ]
    sections = []
    for index, (title, reference, actual, note) in enumerate(pairs):
        sections.append(f"""
<section class="pair" id="view-{index}" {'hidden' if index else ''}>
  <div class="pair-title"><h2>{title}</h2><p>{note}</p></div>
  <figure><figcaption>已确定的二维参考</figcaption>
    <img src="{ref(reference)}" alt="{title}二维参考"></figure>
  <figure><figcaption>实际 Unity 渲染</figcaption>
    <img src="{actual}" alt="{title}Unity实际画面"></figure>
</section>""")
    details = "\n".join(
        f'<a href="{html.escape(name)}"><img loading="lazy" src="{html.escape(name)}" '
        f'alt="{html.escape(name)}"><span>{html.escape(name)}</span></a>'
        for name in sorted(images) if int(name[:2]) >= 7
    )
    tabs = "\n".join(
        f'<button type="button" data-view="{index}" aria-pressed="{str(index == 0).lower()}">{pair[0]}</button>'
        for index, pair in enumerate(pairs)
    )
    page = f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blender → Unity · 形象对照</title>
<style>
:root{{font:16px/1.65 system-ui,sans-serif;color:#dfe7ed;background:#10171d}}
body{{max-width:1260px;margin:0 auto;padding:28px}}
h1{{font-size:30px;margin:0 0 8px}} h2{{font-size:20px;margin:0}}
p{{color:#aabcc9;margin:4px 0 18px}}a{{color:#89c7ee}}
nav{{display:flex;gap:10px;flex-wrap:wrap;margin:22px 0}}
button{{font:inherit;padding:8px 20px;border:1px solid #49616f;border-radius:7px;background:#1a2933;color:inherit;cursor:pointer}}
button[aria-pressed=true]{{background:#d7eaf6;color:#11232e}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
.pair[hidden]{{display:none}} .pair-title{{grid-column:1/-1}}
figure{{margin:0;border:1px solid #304652;border-radius:9px;overflow:hidden;background:#19252e}}
figcaption{{padding:9px 16px}}figure img{{width:100%;height:660px;object-fit:contain;display:block;background:#0b1015}}
.details{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}}
.details a{{display:block;overflow:hidden;border:1px solid #304652;border-radius:7px;text-decoration:none}}
.details img{{width:100%;height:260px;object-fit:contain;display:block;background:#19252e}}
.details span{{display:block;font-size:12px;padding:7px;word-break:break-word}}
footer{{border-top:1px solid #304652;margin-top:28px;padding-top:18px;color:#aabcc9}}
@media(max-width:700px){{body{{padding:16px}}figure img{{height:420px}}.pair{{gap:8px}}h1{{font-size:25px}}}}
</style>
<h1>Blender → Unity · 形象对照</h1>
<p>左侧是建模参考，右侧是实际三维模型的 Unity 渲染。图片保持原样，可点击下方细节图查看原尺寸。</p>
<nav aria-label="选择形象">{tabs}</nav>
{''.join(sections)}
<h2 style="margin:30px 0 14px">实际模型细节与配饰</h2>
<div class="details">{details}</div>
<footer>Unity {html.escape(report["unityVersion"])} · 已完成 {len(report["states"])} 个外观状态与
{len(report["detailViews"])} 个细节视图的导入检查，包含切回原实验角色。
技术检查不等于用户已确认相似度；新模型尚未完成 PICO 真机性能与佩戴视角验证。
<br><a href="checks.json">检查记录</a> · <a href="../blender-workbench/Liang-review.blend">可编辑 Blender 工程</a>
</footer>
<script>
for(const button of document.querySelectorAll('button[data-view]')) {{
 button.addEventListener('click',()=>{{
  for(const panel of document.querySelectorAll('.pair')) panel.hidden=panel.id!=='view-'+button.dataset.view;
  for(const item of document.querySelectorAll('button[data-view]')) item.setAttribute('aria-pressed',String(item===button));
 }});
}}
</script></html>"""
    output = directory / "index.html"
    output.write_text(page, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
