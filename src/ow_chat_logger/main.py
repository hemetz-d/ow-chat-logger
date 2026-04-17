import argparse
from typing import Sequence

from ow_chat_logger.analysis import run_analyze
from ow_chat_logger.benchmark import run_benchmark
from ow_chat_logger.live_runtime import run_live_logger


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ow-chat-logger")
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical interface.",
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Enable periodic live runtime metrics logging.",
    )
    parser.add_argument(
        "--metrics-interval",
        type=float,
        help="Metrics summary interval in seconds for live logging.",
    )
    parser.add_argument(
        "--metrics-log-path",
        help="Metrics CSV path. Relative paths are resolved under the app log dir.",
    )
    parser.add_argument(
        "--ocr-profile",
        help="OCR profile name to use for live runtime when no subcommand is provided.",
    )
    subparsers = parser.add_subparsers(dest="command")

    analyze = subparsers.add_parser(
        "analyze",
        help="Run the OCR pipeline against a saved screenshot and emit debug artifacts.",
    )
    analyze.add_argument("--image", required=True, help="Path to the screenshot image.")
    analyze.add_argument(
        "--output-dir",
        help="Directory for generated debug artifacts. Defaults under the app debug folder.",
    )
    analyze.add_argument(
        "--config",
        help="Optional JSON config override file for this analysis run.",
    )
    analyze.add_argument(
        "--ocr-profile",
        help="OCR profile name to use for this analysis run.",
    )

    benchmark = subparsers.add_parser(
        "benchmark",
        help="Benchmark OCR profiles against screenshot regression fixtures.",
    )
    benchmark.add_argument(
        "--fixtures",
        help="Directory containing regression fixture PNG/expected JSON pairs.",
    )
    benchmark.add_argument(
        "--profiles",
        nargs="+",
        help="OCR profile names to benchmark. Defaults to the built-in comparison set.",
    )
    benchmark.add_argument(
        "--benchmark-config",
        help="Optional JSON config override file used while benchmarking.",
    )
    benchmark.add_argument(
        "--json-out",
        help="Optional path for a JSON benchmark report.",
    )
    benchmark.add_argument(
        "--csv-out",
        help="Optional path for a CSV benchmark report.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.gui:
        from ow_chat_logger.gui.app import run_gui

        return run_gui()
    if args.command == "analyze":
        return run_analyze(args)
    if args.command == "benchmark":
        return run_benchmark(args)
    return run_live_logger(
        metrics_enabled_override=True if args.metrics else None,
        metrics_interval_override=args.metrics_interval,
        metrics_log_path_override=args.metrics_log_path,
        ocr_profile_override=args.ocr_profile,
    )


if __name__ == "__main__":
    raise SystemExit(main())
