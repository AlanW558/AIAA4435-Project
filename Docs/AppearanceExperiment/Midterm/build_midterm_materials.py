"""Assemble the handoff from reviewed prose, authoritative questions and publication evidence."""
from pathlib import Path
import base64
import hashlib
import html
import json
import re

ROOT = Path(__file__).resolve().parent
SURVEY = ROOT.parent / "Study" / "survey"
spec = json.loads((SURVEY / "questionnaire_unified.json").read_text())
pub = json.loads((SURVEY / "publication_status.json").read_text())
assert pub["publication_status"] == "published"
assert pub["questionnaire_id"] == "389439995"
assert pub["public_url"].startswith("https://")
assert pub["answers_submitted_by_agent"] == 0
questions = [q for p in spec["pages"] for q in p["questions"]]
assert len(questions) == 32
assert [q["number"] for q in questions if q["required"]] == [1, 2, 3]
assert len(spec["pages"]) == 6

url = pub["public_url"]
qr_path = SURVEY / "wjx_389439995_qr.png"
qr = qr_path.read_bytes()
assert hashlib.sha256(qr).hexdigest() == pub["qr_code_sha256"]
publication = f"""## 当前填写入口

问卷星编号389439995，已发布、正在运行。平台显示发布时间为2026年10月19日20:59（分钟精度）；核验于{pub['verified_at']}，观察到0答卷，代理未提交任何答卷。

- [参与者填写链接]({url})
- [问卷星官方二维码](../Study/survey/wjx_389439995_qr.png)
- [发布核验记录](../Study/survey/publication_status.md)

![问卷星官方填写二维码](../Study/survey/wjx_389439995_qr.png)

公开首页已在台式机内置浏览器打开并核对，32题六页、仅Q1至Q3必答。状态和答卷数是上述核验时点的观察，不代表之后一直没有新回答。"""

full = ["### 问卷标题", "", spec["title"], "", "### 开头说明", "", spec["description"], "", "### 研究说明", ""]
full += [f"{i}. {t}" for i, t in enumerate(spec["study_information"], 1)]
type_names = {"short_text": "单行文本", "long_text": "多行文本", "rating": "普通单选（1至7及无法判断）", "single_choice": "普通单选"}
mapping = ["| 题号 | 页面 | 字段 | 用途/类型 |", "|---|---|---|---|"]
for page_idx, page in enumerate(spec["pages"], 1):
    full += ["", f"### 第{page_idx}页：{page['title']}", "", page["description"], ""]
    for q in page["questions"]:
        full += [f"#### Q{q['number']}｜{q['title']}", "", f"类型：{type_names[q['type']]}；{'必答' if q['required'] else '选填'}。"]
        if q.get("max_length"):
            full += [f"长度上限：{q['max_length']}字。"]
        if q.get("help"):
            full += ["", f"帮助文字：{q['help']}"]
        if q.get("options"):
            full += ["", "选项（固定顺序，无默认选择）：", ""]
            full += [f"- {o['label']}" for o in q["options"]]
        conditions = q.get("display_conditions", [])
        condition_text = "Q3选择“我同意参加。”，且Q6选择“同意，我可以提供已有的匿名编号。”" if len(conditions) == 2 else ("Q3选择“我同意参加。”" if conditions else "始终显示")
        full += ["", f"显示条件：{condition_text}。", f"字段：`{q['id']}`。", ""]
        if q["number"] == 3:
            full += ["跳转：选择不同意后结束作答，不进入研究问题；线上结束区域仍有提交控件，保存行为未验证。", ""]
        mapping.append(f"| Q{q['number']} | {page['title']} | `{q['id']}` | {type_names[q['type']]} |")

narrative = (ROOT / "design_narrative.md").read_text()
md = narrative.replace("{{PUBLICATION}}", publication).replace("{{FULL_QUESTIONNAIRE}}", "\n".join(full)).replace("{{FIELD_MAP}}", "\n".join(mapping))
assert "{{" not in md
assert len(re.findall(r"^#### Q\d+｜", md, re.M)) == 32
assert "—" not in md and "–" not in md
(ROOT / "问卷完整设计与题目.md").write_text(md)

qr_data = base64.b64encode(qr).decode()
publication_card = f'''<div class="publication"><img src="data:image/png;base64,{qr_data}" alt="问卷星官方二维码"><div><strong>虚拟角色外形修改研究（全流程）</strong><p><a href="{html.escape(url)}">{html.escape(url)}</a></p><p class="small">问卷编号389439995<br>2026年10月19日20:59发布<br>21:02核验：已发布、0答卷<br>32题 · 六页 · 一人最后提交一次</p></div></div>'''
content = (ROOT / "design_brief_content.html").read_text().replace("{{PUBLICATION_CARD}}", publication_card)
assert "{{" not in content
assert "—" not in content and "–" not in content
font_path = Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf")
font_data = base64.b64encode(font_path.read_bytes()).decode()
style = """
@font-face{font-family:Chinese;src:url(data:font/ttf;base64,FONTDATA) format('truetype');font-weight:100 900}
@page{size:A4;margin:0}*{box-sizing:border-box}body{margin:0;color:#233436;font-family:Arial,Chinese,sans-serif;font-size:10.5pt;line-height:1.72;background:#fff}a{color:#14665b;text-decoration:none;overflow-wrap:anywhere}.page{width:210mm;height:297mm;padding:17mm 18mm 19mm;page-break-after:always;position:relative;overflow:hidden}.page:last-child{page-break-after:auto}.kicker{color:#14665b;font-size:9pt;letter-spacing:1.5px;margin-bottom:8mm;border-top:2px solid #14665b;padding-top:3mm}h1{font-size:25pt;line-height:1.35;font-weight:700;color:#153f3c;margin:0 0 6mm}h2{font-size:13pt;line-height:1.4;margin:5mm 0 2mm;color:#153f3c}p{margin:0 0 3mm}.lede{font-size:15pt;line-height:1.7;margin-bottom:7mm}.callout{background:#ecf4f2;border-left:3px solid #3f8a7f;padding:3.5mm 4mm;margin:4mm 0}.callout p:last-child{margin-bottom:0}.meta{font-size:8.6pt;color:#647674;line-height:1.8;margin-top:6mm}.small{font-size:9.1pt;line-height:1.7}table{border-collapse:collapse;width:100%;font-size:10pt;line-height:1.65;margin:3mm 0 4mm}th{background:#e7f0ee;text-align:left;color:#254e49;font-weight:700}th,td{padding:2.2mm 2.6mm;vertical-align:top;border-bottom:1px solid #d9e3e1}td:first-child{min-width:26mm}.compact{font-size:9.7pt}.compact td:first-child{width:38mm}.flow{display:flex;align-items:center;gap:1.8mm;font-size:9.2pt;margin:5mm 0}.flow span{background:#eaf2f0;border:1px solid #d0e2de;padding:2.5mm 2.4mm;border-radius:2mm}.flow b{color:#327669}.numbers{display:flex;gap:4mm;margin:6mm 0}.numbers div{background:#f1f6f5;padding:4mm;width:33.33%}.numbers strong{display:block;color:#14665b;font-size:28pt;line-height:1.2}.numbers span{font-size:10pt}.questions{background:#f5f7f7;padding:3.5mm 5mm 3.5mm 10mm}.questions li{margin:1mm 0}ol{padding-left:6mm;margin:2mm 0 4mm}li{padding-left:1mm;margin-bottom:2mm}.publication{display:flex;align-items:center;gap:7mm;padding:4mm;background:#eff5f3;border:1px solid #dae7e2;margin-bottom:6mm}.publication img{width:47mm;height:47mm;object-fit:contain}.publication p{margin-top:2mm}.references{font-size:9pt;line-height:1.65}.references p{margin-bottom:4mm}.footer{position:absolute;bottom:10mm;left:18mm;right:18mm;border-top:1px solid #dbe5e2;padding-top:2mm;color:#6f7e7c;font-size:8pt;display:flex;justify-content:space-between}
""".replace("FONTDATA", font_data)
chunks=content.split('</section>')
total=len(chunks)-1
for i in range(total):
    chunks[i]+=f'<div class="footer"><span>AIAA4435 · 问卷设计说明 · 2026.10.19</span><span>{i+1} / {total}</span></div></section>'
document='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>外形修改实验：问卷设计说明</title><style>'+style+'</style></head><body>'+''.join(chunks)+'</body></html>'
(ROOT / "问卷设计说明_中期汇报.html").write_text(document)
manifest={"questionnaire_id":pub["questionnaire_id"],"public_url":url,"questionnaire_revision":spec["content_revision"],"question_count":32,"page_count":6,"required_question_numbers":[1,2,3],"pdf_expected_pages":total,"source_sha256":{str(p.relative_to(ROOT.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SURVEY/'questionnaire_unified.json',SURVEY/'publication_status.json',ROOT/'design_narrative.md',ROOT/'design_brief_content.html']},"pdf_render_status":"pending"}
(ROOT/'materials_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({"question_count":len(questions),"markdown_characters":len(md),"html_pages":total,"output_directory":str(ROOT)},ensure_ascii=False))
