"""Export LxM match replay as GIF or MP4."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from viewer.exporters.tictactoe import TicTacToeFrameRenderer
from viewer.exporters.chess import ChessFrameRenderer

RENDERERS = {
    "tictactoe": TicTacToeFrameRenderer,
    "chess": ChessFrameRenderer,
}


def load_match(match_dir: Path):
    config = json.loads((match_dir / "match_config.json").read_text())
    log = json.loads((match_dir / "log.json").read_text())
    result_path = match_dir / "result.json"
    result = json.loads(result_path.read_text()) if result_path.exists() else None
    accepted = [e for e in log if e.get("result") == "accepted"]
    return config, accepted, result


def generate_frames(renderer, config, accepted, result):
    """Generate all PIL Image frames for the match."""
    agents = config.get("agents", [])
    total = len(accepted)
    state = renderer.initial_state(config)
    frames = []

    # Initial state frame
    frames.append(renderer.render_frame(state, 0, total, agents, None))

    # Each move
    for i, entry in enumerate(accepted):
        state = renderer.apply_move(state, entry)
        frames.append(renderer.render_frame(state, i + 1, total, agents, entry))

    # Result frame
    if result:
        frames.append(renderer.render_result_frame(state, result, agents, total))

    return frames


def export_gif(frames, output_path: str, frame_duration_ms: int, result_hold_ms: int):
    """Export frames as animated GIF."""
    if not frames:
        print("No frames to export")
        return

    durations = []
    # First frame (initial state) held longer
    durations.append(frame_duration_ms * 2)
    # Move frames
    for _ in range(len(frames) - 2 if len(frames) > 2 else len(frames) - 1):
        durations.append(frame_duration_ms)
    # Last frame (result) held longer
    if len(frames) > 1:
        durations.append(result_hold_ms)

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    print(f"GIF saved: {output_path} ({len(frames)} frames)")


def export_mp4(frames, output_path: str, frame_duration_ms: int, result_hold_ms: int):
    """Export frames as MP4 using ffmpeg."""
    if not shutil.which("ffmpeg"):
        print("Error: ffmpeg not found. Install it for MP4 export.")
        print("  brew install ffmpeg  (macOS)")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Write frames as PNGs, duplicating for duration control
        fps = 4  # 4 fps base
        frame_idx = 0

        def write_copies(img, duration_ms):
            nonlocal frame_idx
            n_copies = max(1, round(duration_ms / 1000 * fps))
            for _ in range(n_copies):
                img.save(tmpdir / f"frame_{frame_idx:04d}.png")
                frame_idx += 1

        # Initial state
        write_copies(frames[0], frame_duration_ms * 2)
        # Move frames
        for f in frames[1:-1] if len(frames) > 2 else frames[1:]:
            write_copies(f, frame_duration_ms)
        # Result frame
        if len(frames) > 1:
            write_copies(frames[-1], result_hold_ms)

        # Run ffmpeg
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(tmpdir / "frame_%04d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "23",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ffmpeg error: {result.stderr}")
            sys.exit(1)

        print(f"MP4 saved: {output_path} ({frame_idx} total frames at {fps}fps)")


def main():
    parser = argparse.ArgumentParser(description="Export LxM match replay")
    parser.add_argument("--match", required=True, help="Match ID or path to match folder")
    parser.add_argument("--format", choices=["gif", "mp4"], default="gif")
    parser.add_argument("--output", "-o", default=None, help="Output file path")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier")
    parser.add_argument("--resolution", default="800x600", help="Frame resolution WxH")
    args = parser.parse_args()

    # Find match directory
    match_dir = Path(args.match)
    if not match_dir.exists():
        match_dir = Path("matches") / args.match
    if not match_dir.exists():
        print(f"Match not found: {args.match}")
        sys.exit(1)

    config, accepted, result = load_match(match_dir)
    game_name = config.get("game", {}).get("name", "unknown")

    RendererClass = RENDERERS.get(game_name)
    if not RendererClass:
        print(f"No renderer for game: {game_name}")
        sys.exit(1)

    renderer = RendererClass()
    frames = generate_frames(renderer, config, accepted, result)

    # Timing
    base_duration = int(1500 / args.speed)
    result_hold = int(3000 / args.speed)

    # Output path
    output = args.output or f"{config.get('match_id', 'replay')}.{args.format}"

    if args.format == "gif":
        export_gif(frames, output, base_duration, result_hold)
    else:
        export_mp4(frames, output, base_duration, result_hold)


if __name__ == "__main__":
    main()
