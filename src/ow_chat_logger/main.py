import argparse
from typing import Sequence

from ow_chat_logger.analysis import run_analyze
from ow_chat_logger.live_runtime import run_live_logger


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ow-chat-logger")
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "analyze":
        return run_analyze(args)
    return run_live_logger(
        metrics_enabled_override=True if args.metrics else None,
        metrics_interval_override=args.metrics_interval,
        metrics_log_path_override=args.metrics_log_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
