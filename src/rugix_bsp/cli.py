"""CLI entry point for rugix-bsp."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rugix_bsp.models import Board, FamilyRelease
from rugix_bsp.registry import build_matrix, discover_all


def _resolve_board_release(
    args: argparse.Namespace,
) -> list[tuple[Board, FamilyRelease]]:
    """Resolve a board name (and optional release) to build matrix entries."""
    boards = discover_all()
    matching = [b for b in boards if b.name == args.board]
    if not matching:
        print(f"Unknown board: {args.board}")
        print(f"Available: {', '.join(sorted(b.name for b in boards))}")
        sys.exit(1)
    board = matching[0]

    matrix = build_matrix([board])
    release_name = getattr(args, "release", None)
    if release_name:
        matrix = [(b, r) for b, r in matrix if r.name == release_name]
        if not matrix:
            releases = ", ".join(board.family.releases)
            print(f"Unknown release: {release_name}")
            print(f"Available for {board.name}: {releases}")
            sys.exit(1)
    return matrix


def cmd_list(args: argparse.Namespace) -> None:
    """List all available boards and releases."""
    boards = discover_all()
    if not boards:
        print("No boards found.")
        return

    matrix = build_matrix(boards)
    for board, release in sorted(matrix, key=lambda x: (x[0].name, x[1].name)):
        print(
            f"  {board.name:<30} {release.name:<20} "
            f"{board.support:<12} {board.machine}"
        )


def cmd_build(args: argparse.Namespace) -> None:
    """Build a BSP for a specific board."""
    from rugix_bsp.extract import extract_bsp
    from rugix_bsp.hashing import compute_build_hash
    from rugix_bsp.kas.runner import KasRunner

    work_dir = Path(args.work_dir)
    output_dir = Path(args.output_dir)

    for board, release in _resolve_board_release(args):
        runner = KasRunner(board, release, work_dir=work_dir / board.name)
        print(f"Building {board.name} (release={release.name})...")
        deploy_dir = runner.build()
        resolved = runner.resolve()

        build_hash = compute_build_hash(
            board, release, runner.layer_dir, runner.kas_lock_path
        )

        output = output_dir / f"{board.name}_{release.name}.bsp.tar.gz"
        print(f"Extracting BSP artifacts from {deploy_dir}...")
        bsp = extract_bsp(
            board,
            release,
            resolved,
            deploy_dir,
            output,
            kas_config=runner.kas_config_path,
            kas_lock=runner.kas_lock_path,
            layer_dir=runner.layer_dir,
            build_dir=runner.build_dir,
            build_hash=build_hash,
        )
        print(f"BSP archive: {bsp}")


def cmd_build_all(args: argparse.Namespace) -> None:
    """Build BSPs for all boards and releases."""
    from rugix_bsp.extract import extract_bsp
    from rugix_bsp.hashing import compute_build_hash
    from rugix_bsp.kas.runner import KasRunner

    boards = discover_all()
    if not boards:
        print("No boards found.")
        return

    work_dir = Path(args.work_dir)
    output_dir = Path(args.output_dir)
    matrix = build_matrix(boards)

    for board, release in sorted(matrix, key=lambda x: (x[0].name, x[1].name)):
        print(f"\nBuilding {board.name} (release={release.name})...")
        runner = KasRunner(board, release, work_dir=work_dir / board.name)
        deploy_dir = runner.build()
        resolved = runner.resolve()

        build_hash = compute_build_hash(
            board, release, runner.layer_dir, runner.kas_lock_path
        )

        output = output_dir / f"{board.name}_{release.name}.bsp.tar.gz"
        extract_bsp(
            board,
            release,
            resolved,
            deploy_dir,
            output,
            kas_config=runner.kas_config_path,
            kas_lock=runner.kas_lock_path,
            layer_dir=runner.layer_dir,
            build_dir=runner.build_dir,
            build_hash=build_hash,
        )
        print(f"BSP archive: {output}")

    print(f"\nAll {len(matrix)} BSPs built.")


def cmd_hash(args: argparse.Namespace) -> None:
    """Print the content hash for a board + release."""
    from rugix_bsp.hashing import compute_build_hash
    from rugix_bsp.kas.runner import KasRunner

    work_dir = Path(args.work_dir)

    for board, release in _resolve_board_release(args):
        runner = KasRunner(board, release, work_dir=work_dir / board.name)
        runner.generate_config()
        build_hash = compute_build_hash(board, release, runner.layer_dir)
        print(f"{board.name}\t{release.name}\t{build_hash}")


def cmd_kas_config(args: argparse.Namespace) -> None:
    """Generate Kas config without building (for debugging)."""
    from rugix_bsp.kas.runner import KasRunner

    work_dir = Path(args.work_dir)

    for board, release in _resolve_board_release(args):
        runner = KasRunner(board, release, work_dir=work_dir / board.name)
        config_path = runner.generate_config()
        print(f"{board.name} ({release.name}): {config_path}")


def _parse_archive_name(
    filename: str, boards: list[Board]
) -> tuple[Board, str] | None:
    """Parse board name and release from a <board>_<release>.bsp.tar.gz filename."""
    stem = filename.removesuffix(".tar.gz").removesuffix(".bsp")
    parts = stem.split("_", 1)
    if len(parts) != 2:
        return None
    board_name, release = parts
    matching = [b for b in boards if b.name == board_name]
    if not matching:
        return None
    return matching[0], release


def cmd_push(args: argparse.Namespace) -> None:
    """Push a BSP archive to an OCI registry."""
    from datetime import date

    from rugix_bsp.distribute import push_bsp

    archive = Path(args.archive)
    if not archive.exists():
        print(f"Archive not found: {archive}")
        sys.exit(1)

    boards = discover_all()

    if args.board:
        matching = [b for b in boards if b.name == args.board]
        if not matching:
            print(f"Unknown board: {args.board}")
            sys.exit(1)
        board = matching[0]
        release = args.release or list(board.family.releases.keys())[0]
    else:
        parsed = _parse_archive_name(archive.name, boards)
        if parsed is None:
            print(f"Could not determine board from: {archive.name}")
            print("Use --board and --release to specify.")
            sys.exit(1)
        board, release = parsed

    if args.release:
        release = args.release
    version = args.version or date.today().strftime("%Y.%m.%d")

    ref = push_bsp(archive, board, release, version, registry=args.registry)
    print(f"Pushed: {ref}")


def cmd_detect_changes(args: argparse.Namespace) -> None:
    """Output a JSON build matrix of boards that need rebuilding."""
    from rugix_bsp.hashing import compute_build_hash
    from rugix_bsp.kas.runner import KasRunner

    boards = discover_all()
    matrix = build_matrix(boards)
    work_dir = Path(args.work_dir)

    changed: list[dict[str, str]] = []
    for board, release in matrix:
        runner = KasRunner(board, release, work_dir=work_dir / board.name)
        runner.generate_config()
        build_hash = compute_build_hash(board, release, runner.layer_dir)
        # TODO: check if hash exists in registry
        changed.append(
            {"board": board.name, "release": release.name, "hash": build_hash}
        )

    print(json.dumps(changed))


def cmd_manifest_to_kas(args: argparse.Namespace) -> None:
    """Convert a repo manifest XML to Kas repo entries."""
    import yaml

    from rugix_bsp.kas.manifest import parse_repo_manifest

    exclude = set(args.exclude.split(",")) if args.exclude else set()
    repos = parse_repo_manifest(args.manifest, exclude=exclude)

    if args.format == "yaml":
        print(yaml.dump({"repos": repos}, default_flow_style=False, sort_keys=False))
    else:
        print(json.dumps(repos, indent=2))


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Rugix BSP builder")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List available boards and releases")

    p_build = sub.add_parser("build", help="Build BSP for a board")
    p_build.add_argument("board", help="Board name")
    p_build.add_argument("--release", help="Release name (default: all)")
    p_build.add_argument("--work-dir", default="build")
    p_build.add_argument("--output-dir", default="output")

    p_all = sub.add_parser("build-all", help="Build BSPs for all boards")
    p_all.add_argument("--work-dir", default="build")
    p_all.add_argument("--output-dir", default="output")

    p_hash = sub.add_parser("hash", help="Print content hash for a board")
    p_hash.add_argument("board", help="Board name")
    p_hash.add_argument("--release", help="Release name (default: all)")
    p_hash.add_argument("--work-dir", default="build")

    p_kas = sub.add_parser("kas-config", help="Generate Kas config (debug)")
    p_kas.add_argument("board", help="Board name")
    p_kas.add_argument("--release", help="Release name (default: all)")
    p_kas.add_argument("--work-dir", default="build")

    p_push = sub.add_parser("push", help="Push BSP to OCI registry")
    p_push.add_argument("archive", help="Path to .bsp.tar.gz")
    p_push.add_argument("--board", help="Board name (auto-detected from filename)")
    p_push.add_argument("--release", help="Release name")
    p_push.add_argument("--version", help="Version tag (default: today's date)")
    p_push.add_argument("--registry", default="ghcr.io/rugix/rugix-bsps")

    p_detect = sub.add_parser(
        "detect-changes", help="Output JSON matrix of changed boards"
    )
    p_detect.add_argument("--registry", default="ghcr.io/rugix/rugix-bsps")
    p_detect.add_argument("--work-dir", default="build")

    p_manifest = sub.add_parser(
        "manifest-to-kas",
        help="Convert a repo manifest XML to Kas repos",
    )
    p_manifest.add_argument("manifest", help="Path to manifest XML file")
    p_manifest.add_argument(
        "--exclude",
        default="",
        help="Comma-separated repo keys to exclude (e.g., base,fsl-community-bsp-base)",
    )
    p_manifest.add_argument(
        "--format",
        choices=["yaml", "json"],
        default="yaml",
        help="Output format (default: yaml)",
    )

    args = parser.parse_args(argv)

    commands = {
        "list": cmd_list,
        "build": cmd_build,
        "build-all": cmd_build_all,
        "hash": cmd_hash,
        "kas-config": cmd_kas_config,
        "push": cmd_push,
        "detect-changes": cmd_detect_changes,
        "manifest-to-kas": cmd_manifest_to_kas,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
