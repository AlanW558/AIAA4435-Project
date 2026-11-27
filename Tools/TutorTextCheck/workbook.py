#!/usr/bin/env python3
"""Generate/parse the unchanged 32-task engineering request worksheet.

This module never calls a provider, executes requests, or changes study material.
Editable text is delimited by HTML comments rather than Markdown headings.
Exactly one structural line break is removed at each field boundary; all other
user whitespace and Markdown are preserved. Never overwrite a completed sheet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "Assets/Project/Resources/Tutor/StudyTaskSequence.json"
FIELDS = ("request", "clarify", "clarification")
SCENARIOS = {
    "C1": "Explicit target / 明确目标",
    "C2": "Degree or qualitative preference / 程度或定性偏好",
    "C3": "Potentially different interpretations / 可能存在不同解释",
    "C4": "History, preference or partial restoration / 历史、偏好或局部恢复",
}
MARKER = re.compile(
    r"<!--\s*(?P<close>/)?(?P<field>request|clarify|clarification):"
    r"(?P<code>[A-Za-z0-9_-]+)\s*-->"
)


def catalog():
    """Return the actual registered catalog, ordered tasks and byte checksum."""
    raw = CATALOG_PATH.read_bytes()
    value = json.loads(raw)
    tasks = [
        {**task, "domain": module["direction"], "module_title": module["title"]}
        for module in value["modules"]
        for task in module["tasks"]
    ]
    codes = [task["task_code"] for task in tasks]
    if len(tasks) != 32 or len(set(codes)) != 32:
        raise ValueError("The worksheet requires exactly the current 32 unique tasks.")
    return value, tasks, hashlib.sha256(raw).hexdigest()


def _quote(text):
    return "\n".join("> " + line if line else ">" for line in text.splitlines())


def render():
    value, tasks, checksum = catalog()
    parts = [
        "# 四属性任务 Request 填写表\n",
        "这是当前版本的四属性任务与 Request 文件。"
        "每题独立使用题库规定的起点；历史题使用给定示例历史，不继承上一题结果。\n",
        "你可以一次填写全部任务，也可以先填写部分任务，未填写的 Request 留空。"
        "请使用自己的英文表达，不必照抄任务目标；也不必故意省略信息或制造歧义。"
        "任务卡及预期目标只给你看，不会自动作为 request 发送给模型。\n",
        "每题有三个填写区域：\n\n"
        "1. **Request**：由你填写希望提交的英文原文。\n"
        "2. **Clarify**：先留空，运行后由工具写入实际需要回答的澄清，标明策略。\n"
        "3. **Clarification**：看到澄清后再填写；如果有多个策略，请分别使用 `A: ...`、"
        "`N: ...`、`S: ...`（或工具实际列出的策略）作答，不用同一句自动代答其它策略。\n",
        "请在对应 HTML 注释之间填写，保留注释、题号及其余题目材料。"
        "每个区域可以写多行，也可以使用 Markdown；程序会保留你的实际文字。"
        "澄清尚未出现时请勿提前猜写答案。需要进一步澄清时，工具会另行保留该轮记录。\n",
        "**保持要求：** Use your own words to ask the tutor for the change. "
        "You may mention any details you consider useful. Keep all settings not targeted by this task unchanged.\n",
        "**音色名称：** Female voice 1/2/3 与 Male voice 1/2。没有固定试听例子；提交后聆听模型实际生成的回复。\n",
        f"材料版本：`{value['materials_version']}`；任务清单：`{value['version']}`；共 32 题。\n\n"
        f"<!-- catalog-sha256:{checksum} -->\n",
    ]
    for task in tasks:
        code = task["task_code"]
        display_code = task.get('display_code', code)
        parts.extend([
            f"## {display_code} · {task['module_title']} · {task['scenario']}\n",
            f"情境：{SCENARIOS[task['scenario']]}\n",
            f"**Task goal:** {task['instructions']}\n",
            f"**Keep unchanged:** {task['keep_unchanged']}\n",
            f"**Request example:** {task['request_example']}\n",
        ])
        for field, label in (
            ("request", "Request — 你填写"),
            ("clarify", "Clarify — 工具填写，先留空"),
            ("clarification", "Clarification — 看到澄清后由你填写"),
        ):
            parts.append(f"**{label}:**\n\n<!-- {field}:{code} -->\n\n<!-- /{field}:{code} -->\n")
    return "\n".join(parts)


def generate(path):
    """Create a new worksheet; refuse existing paths, including symlinks."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(render())
    return path


def _field_text(raw):
    # These line breaks belong to the worksheet's markers, not the request.
    # Do not strip spaces, additional line breaks, or Markdown from user input.
    if raw.startswith("\r\n"):
        raw = raw[2:]
    elif raw.startswith("\n"):
        raw = raw[1:]
    else:
        raise ValueError("A field must begin on the line after its opening marker.")
    if raw.endswith("\r\n"):
        raw = raw[:-2]
    elif raw.endswith("\n"):
        raw = raw[:-1]
    else:
        raise ValueError("A closing marker must be on a new line after its field.")
    return raw


def parse(path):
    """Return {task_code: {request, clarify, clarification}}, preserving text.

    The ordered field markers are structural. Unknown, missing, duplicated,
    reordered, nested or unclosed field markers are rejected before execution.
    Headings within a user's text are not treated as new tasks.
    """
    with Path(path).open(encoding="utf-8", newline="") as stream:
        text = stream.read()
    return _parse_text(text)


def _parse_text(text):
    """Validate worksheet structure and return its editable fields."""
    _, tasks, checksum = catalog()
    hashes = re.findall(r"<!--\s*catalog-sha256:([a-f0-9]{64})\s*-->", text)
    if hashes != [checksum]:
        raise ValueError("The task catalog changed or its worksheet checksum is missing/duplicated.")
    markers = list(MARKER.finditer(text))
    expected = [(task["task_code"], field, close)
                for task in tasks for field in FIELDS for close in (False, True)]
    observed = [(m["code"], m["field"], bool(m["close"])) for m in markers]
    if observed != expected:
        raise ValueError("Expected exactly 32 tasks and one matching marker pair for each of the three fields, in catalog order.")
    result = {task["task_code"]: {} for task in tasks}
    for begin, end in zip(markers[::2], markers[1::2]):
        result[begin["code"]][begin["field"]] = _field_text(text[begin.end():end.start()])
    # Only headings outside the editable fields are structural task headings.
    outside = text
    for begin, end in reversed(list(zip(markers[::2], markers[1::2]))):
        outside = outside[:begin.end()] + outside[end.start():]
    headings = re.findall(r"^## ([A-Za-z0-9_-]+)\s+·", outside, re.MULTILINE)
    if headings != [task.get('display_code', task['task_code']) for task in tasks]:
        raise ValueError("Task headings must retain the 32 catalog task codes and their order.")
    expected_text = render()
    expected_markers = list(MARKER.finditer(expected_text))
    for begin, end in reversed(list(zip(expected_markers[::2], expected_markers[1::2]))):
        expected_text = expected_text[:begin.end()] + expected_text[end.start():]
    if outside.replace("\r\n", "\n") != expected_text.replace("\r\n", "\n"):
        raise ValueError("Task instructions/context changed. Edit only the three marked fields.")
    return result


def replace_fields(text, replacements):
    """Replace selected fields in memory, preserving every other character.

    ``replacements`` maps ``(task_code, field_name)`` tuples to exact strings.
    Opening/closing structural line endings are retained independently, so CRLF
    worksheets stay CRLF without normalizing new user text. Malformed sheets,
    unknown fields, non-string values and injected structural markers fail
    before a caller can save the returned text. This function never writes files.
    """
    if not isinstance(text, str) or not isinstance(replacements, dict):
        raise ValueError("Use worksheet text and a dictionary of field replacements.")
    current = _parse_text(text)
    allowed = {(code, field) for code in current for field in FIELDS}
    for key, value in replacements.items():
        if (not isinstance(key, tuple) or len(key) != 2
                or not all(isinstance(part, str) for part in key)
                or key not in allowed or not isinstance(value, str)):
            raise ValueError("Replace only registered (task_code, field) pairs with strings.")
    markers = list(MARKER.finditer(text))
    result = text
    for begin, end in reversed(list(zip(markers[::2], markers[1::2]))):
        key = (begin["code"], begin["field"])
        if key not in replacements:
            continue
        raw = text[begin.end():end.start()]
        opening = "\r\n" if raw.startswith("\r\n") else "\n"
        closing = "\r\n" if raw.endswith("\r\n") else "\n"
        result = result[:begin.end()] + opening + replacements[key] + closing + result[end.start():]
    parsed = _parse_text(result)
    if any(parsed[code][field] != value for (code, field), value in replacements.items()):
        raise ValueError("Replacement text did not preserve the intended field value.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("generate", "check"):
        sub.add_parser(command).add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.path)
    fields = parse(args.path)
    print(json.dumps({"path": str(args.path.resolve()), "tasks": len(fields),
                      "requests_filled": sum(bool(v["request"].strip()) for v in fields.values()),
                      "clarifications_filled": sum(bool(v["clarification"].strip()) for v in fields.values()),
                      "provider_calls": 0}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
