"""MCP server for FORGE (Framework for Operational Risk & Governance Enhancement)."""

from __future__ import annotations

import argparse
import os
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from forge_risk_engine import (
    AnalysisSummary,
    analyze_risk_plan,
    benchmark_solvers,
    build_visual_report_markdown,
    prepare_risk_data,
    summary_to_dict,
)

TransportName = Literal["stdio", "streamable-http"]
SolverName = Literal["cp-sat", "pulp"]

LAST_ANALYSIS: AnalysisSummary | None = None


def _store_last(summary: AnalysisSummary) -> AnalysisSummary:
    global LAST_ANALYSIS
    LAST_ANALYSIS = summary
    return summary


def _run_analysis(
    *,
    risks: list[dict[str, Any]] | None = None,
    num_records: int = 15,
    solver: SolverName = "cp-sat",
    deadline: int = 20,
    team_capacity: int = 4,
    target_remaining_ratio: float = 0.5,
    target_score_max: float | None = None,
) -> AnalysisSummary:
    summary = analyze_risk_plan(
        risks=risks,
        num_records=num_records,
        solver=solver,
        deadline=deadline,
        team_capacity=team_capacity,
        target_remaining_ratio=target_remaining_ratio,
        target_score_max=target_score_max,
    )
    return _store_last(summary)


def create_mcp_server(
    *,
    host: str,
    port: int,
    streamable_http_path: str,
    log_level: str,
) -> FastMCP:
    mcp = FastMCP(
        name="FORGE Risk Intelligence",
        instructions=(
            "FORGE server for operational, financial and cyber risk intelligence. "
            "Use these tools to optimize remediation schedules and generate D3 visual reports."
        ),
        host=host,
        port=port,
        streamable_http_path=streamable_http_path,
        log_level=log_level.upper(),
    )

    @mcp.tool(
        name="forge_get_risk_dataset",
        description=(
            "Return FORGE sample risk records (or validated custom records), including total risk score and budget baseline."
        ),
    )
    def forge_get_risk_dataset(
        num_records: int = 15,
        risks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        df = prepare_risk_data(risks=risks, num_records=num_records)
        return {
            "num_records": int(len(df)),
            "total_score": float(df["Score"].sum()),
            "total_residual_floor": float(df["Res_Score"].sum()),
            "total_cta_if_all_remediated": float(df["CTA"].sum()),
            "risks": df.to_dict(orient="records"),
        }

    @mcp.tool(
        name="forge_optimize_schedule",
        description=(
            "Optimize remediation plan cost while meeting target score, deadline, capacity, and predecessor constraints."
        ),
    )
    def forge_optimize_schedule(
        num_records: int = 15,
        solver: SolverName = "cp-sat",
        deadline: int = 20,
        team_capacity: int = 4,
        target_remaining_ratio: float = 0.5,
        target_score_max: float | None = None,
        risks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        summary = _run_analysis(
            risks=risks,
            num_records=num_records,
            solver=solver,
            deadline=deadline,
            team_capacity=team_capacity,
            target_remaining_ratio=target_remaining_ratio,
            target_score_max=target_score_max,
        )
        return summary_to_dict(summary)

    @mcp.tool(
        name="forge_visual_report",
        description=(
            "Generate a markdown report that includes schedule table plus D3 charts for budget timeline and remediation Gantt."
        ),
    )
    def forge_visual_report(
        num_records: int = 15,
        solver: SolverName = "cp-sat",
        deadline: int = 20,
        team_capacity: int = 4,
        target_remaining_ratio: float = 0.5,
        target_score_max: float | None = None,
        risks: list[dict[str, Any]] | None = None,
    ) -> str:
        summary = _run_analysis(
            risks=risks,
            num_records=num_records,
            solver=solver,
            deadline=deadline,
            team_capacity=team_capacity,
            target_remaining_ratio=target_remaining_ratio,
            target_score_max=target_score_max,
        )
        return build_visual_report_markdown(summary)

    @mcp.tool(
        name="forge_visual_report_from_last_run",
        description="Return the last generated FORGE visual report (including D3 charts).",
    )
    def forge_visual_report_from_last_run() -> str:
        if LAST_ANALYSIS is None:
            return (
                "No previous analysis found.\n\n"
                "Run `forge_visual_report` or `forge_optimize_schedule` first."
            )
        return build_visual_report_markdown(LAST_ANALYSIS)

    @mcp.tool(
        name="forge_benchmark_solvers",
        description="Benchmark cp-sat and pulp solver runtimes for the FORGE dataset.",
    )
    def forge_benchmark_solvers(
        iterations: int = 5,
        num_records: int = 15,
        deadline: int = 20,
        team_capacity: int = 4,
        target_remaining_ratio: float = 0.5,
    ) -> dict[str, Any]:
        return benchmark_solvers(
            iterations=iterations,
            num_records=num_records,
            deadline=deadline,
            team_capacity=team_capacity,
            target_remaining_ratio=target_remaining_ratio,
        )

    return mcp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FORGE Risk Intelligence MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=os.getenv("FORGE_MCP_TRANSPORT", "stdio"),
        help="MCP transport to use.",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("FORGE_MCP_HOST", "127.0.0.1"),
        help="Host for streamable-http transport.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("FORGE_MCP_PORT", "8765")),
        help="Port for streamable-http transport.",
    )
    parser.add_argument(
        "--streamable-http-path",
        default=os.getenv("FORGE_MCP_STREAMABLE_HTTP_PATH", "/mcp"),
        help="HTTP path for MCP streamable transport.",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("FORGE_MCP_LOG_LEVEL", "INFO"),
        help="Server log level.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mcp = create_mcp_server(
        host=args.host,
        port=args.port,
        streamable_http_path=args.streamable_http_path,
        log_level=args.log_level,
    )
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
