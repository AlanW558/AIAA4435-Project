#!/usr/bin/env python3
"""Caption a verified, real avatar-v2 desktop recording in English."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timestamp(seconds):
    centiseconds = round(seconds * 100)
    return f"{centiseconds // 360000}:{centiseconds // 6000 % 60:02}:{centiseconds // 100 % 60:02}.{centiseconds % 100:02}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--take", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    take = args.take.resolve()
    event_file = take / "demo-events.json"
    evidence = json.loads(event_file.read_text())
    if not evidence.get("passed") or evidence.get("scenario") != "avatar-v2":
        raise SystemExit("A verified avatar-v2 recording is required.")
    events = evidence["events"]
    if [e["action"] for e in events] != ["submit", "submit", "submit", "answer", "submit", "undo", "finish"]:
        raise SystemExit("Unexpected action sequence; inspect the actual evidence.")
    complete = events[-1]
    if complete["seconds"] >= 59.8 or len(complete["status"]["captures"]) != 4:
        raise SystemExit("The recording does not show all completion checks.")
    source = take / evidence["raw_video"]
    if args.output.exists():
        raise SystemExit("Output already exists; preserve it and choose a new path.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    styles = (ROOT / "StudyData/pico/desktop-demo/captions.ass").read_text().split("[Events]")[0]
    rows = [
        (0, 60, "Title", "APPEARANCE ROOM / EDITABLE AVATARS"),
        (0, 60, "Tag", "DESKTOP RECORDING · DEBUG DEMO"),
        (0, 5, "Caption", "A new 3D avatar with editable clothes, color, accessories, and size."),
        (5, 16, "Caption", "Change into orange sportswear. Keep the avatar, glasses, and size."),
        (16, 25, "Caption", "Set the scale to 1.10. Preserve the other features."),
        (25, events[2]["seconds"], "Caption", 'Request a "cool color" without changing the outfit.'),
        (events[2]["seconds"], 32, "Caption", '"Cool color" is ambiguous. The system asks which color.'),
        (32, 40, "Caption", "Choose blue. Apply the selected color to the sportswear."),
        (40, events[4]["seconds"], "Caption", "Replace the whole avatar with the yellow mascot."),
        (events[4]["seconds"], 49, "Caption", "The mascot appears with its own default features."),
        (49, 54, "Caption", "Undo the replacement. Restore the human, outfit, color, glasses, and size."),
        (54, complete["seconds"], "Caption", "Finish and check that the rendered appearance stays unchanged."),
        (complete["seconds"], 60, "Caption", "All three persistence checks passed."),
    ]
    # Do not mislabel a slow or reordered take using the intended schedule.
    for index, deadline in ((0, 16), (1, 25), (2, 32), (3, 40), (4, 49), (5, 54)):
        if events[index]["seconds"] >= deadline:
            raise SystemExit("A stage overran its caption window; inspect the take before editing.")
    subtitle = take / "captions-en.ass"
    content = styles + "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    for start, end, style, line in rows:
        if end > start:
            content += f"Dialogue: 1,{timestamp(start)},{timestamp(end)},{style},,0,0,0,,{line}\n"
    subtitle.write_text(content)
    def filter_path(path):
        return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "'\\''")
    video_filter = (
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
        f"subtitles=filename='{filter_path(subtitle)}':fontsdir='{filter_path(ROOT / 'Assets/Project/Fonts')}'"
    )
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "warning", "-i", str(source),
        "-vf", video_filter, "-an", "-c:v", "libx264", "-preset", "medium",
        "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(args.output),
    ], check=True)
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=width,height,avg_frame_rate,nb_frames",
        "-of", "json", str(args.output),
    ]))
    stream = probe["streams"][0]
    if (stream["width"], stream["height"], stream["avg_frame_rate"], stream["nb_frames"]) != (1920, 1080, "30/1", "1800"):
        raise SystemExit("Unexpected final video format.")
    if abs(float(probe["format"]["duration"]) - 60) > .05:
        raise SystemExit("Unexpected final video duration.")
    sources = [
        "Backend/core.py", "Backend/model.py", "Backend/capabilities.py",
        "Assets/Project/Scripts/AppearanceExperiment/AppearanceAvatar.cs",
        "Assets/Project/Scripts/AppearanceExperiment/AppearanceLegacyAvatar.cs",
        "Assets/Project/Scripts/AppearanceExperiment/AppearanceExperimentClient.cs",
        "Assets/Project/Resources/AvatarDemo/Liang.fbx",
        "Assets/Project/Resources/AvatarDemo/Nailong.fbx",
        "Assets/Project/Resources/AvatarDemo/MaskedReferenceLit.shader",
        "Tools/AppearanceExperiment/record_desktop_demo.py",
        "Tools/AppearanceExperiment/finish_avatar_video.py",
        "Tools/AppearanceExperiment/assemble_reference_avatars.py",
        "Tools/AppearanceExperiment/fit_landmark_head_candidate.py",
        "Tools/AppearanceExperiment/repair_neck_candidate.py",
        "Tools/AppearanceExperiment/repair_bare_texture.py",
    ]
    # The FBX depends on external reference albedos and masks. Fingerprint those
    # too, so this recording can be traced to the actual rendered appearance.
    sources.extend(str(path.relative_to(ROOT)) for path in sorted(
        (ROOT / "Assets/Project/Resources/AvatarDemo/Textures").glob("*_Reference_*.png")))
    sources.extend(str(path.relative_to(ROOT)) for path in sorted(
        (ROOT / "Assets/Project/Resources/AvatarDemo/Textures").glob("Fixed_Liang_DetailedHead_*.png")))
    sources.extend(str(path.relative_to(ROOT)) for path in sorted(
        (ROOT / "Assets/Project/Resources/AvatarDemo/Textures").glob("Fixed_LiangNeck_*_Albedo.png")))
    assembly_path = ROOT / "StudyData/avatar-v3/unity-blender-staging/AvatarDemo/assembly.json"
    assembly = json.loads(assembly_path.read_text()) if assembly_path.is_file() else {}
    if assembly:
        sources.append(str(assembly_path.relative_to(ROOT)))
    probe.update(
        sha256=digest(args.output),
        capture_source=evidence["capture_source"],
        phase="debug", capability_profile="avatar-demo-v1", headset_recording=False,
        avatar_asset_revision="reference-reconstruction-v3",
        geometry_revision=assembly.get("geometry_revision", "unrecorded"),
        texture_revision=assembly.get("texture_revision", "unrecorded"),
        subtitle_language="en", subtitle_file=str(subtitle.relative_to(ROOT)),
        subtitle_sha256=digest(subtitle), raw_event_manifest=str(event_file.relative_to(ROOT)),
        event_manifest_sha256=digest(event_file),
        backend_session_id=evidence["initial"]["session_id"],
        source_hashes={name: digest(ROOT / name) for name in sources},
    )
    args.output.with_suffix(".manifest.json").write_text(json.dumps(probe, indent=2) + "\n")
    print(json.dumps(probe, indent=2))


if __name__ == "__main__":
    main()
