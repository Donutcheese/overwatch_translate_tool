"""生成 20 并发、P95 2 秒技术路线图。"""

from pathlib import Path

from graphviz import Digraph


YELLOW = "#f4c320"
BLACK = "#2a2a2a"
WHITE = "#ffffff"


def build_graph() -> Digraph:
    graph = Digraph("ow_translation_route", comment="OW 翻译工具技术路线")
    graph.attr(
        rankdir="TB",
        bgcolor=WHITE,
        pad="0.28",
        nodesep="0.24",
        ranksep="0.48",
        splines="ortho",
        newrank="true",
        compound="true",
        dpi="180",
        outputorder="edgesfirst",
        fontname="Microsoft YaHei",
        label="OW REAL-TIME TRANSLATION  /  20 CONCURRENT  /  P95 ≤ 2s",
        labelloc="t",
        fontsize="18",
        fontcolor=BLACK,
    )
    graph.attr(
        "node",
        shape="box",
        style="rounded,filled",
        fixedsize="true",
        width="2.12",
        height="0.88",
        color=BLACK,
        fillcolor=YELLOW,
        fontcolor=BLACK,
        fontname="Microsoft YaHei",
        fontsize="10",
        margin="0.12,0.08",
        penwidth="1.5",
    )
    graph.attr(
        "edge",
        color=BLACK,
        penwidth="1.5",
        arrowsize="0.68",
    )

    with graph.subgraph(name="cluster_client") as client:
        client.attr(
            label="A  /  CLIENT LOCAL PIPELINE  /  客户端本地感知",
            labeljust="l",
            fontsize="12",
            color=BLACK,
            bgcolor=WHITE,
            fontcolor=BLACK,
            style="rounded",
            penwidth="1.2",
            margin="14",
        )
        with client.subgraph() as client_row:
            client_row.attr(rank="same")
            client_row.node(
                "capture",
                "01  CAPTURE\n截图并立即模糊\n≤ 50ms",
                fillcolor=BLACK,
                fontcolor=WHITE,
            )
            client_row.node(
                "delta",
                "02  DELTA\n感知哈希 + 行差异\n未变化则直接复用",
                fillcolor=WHITE,
            )
            client_row.node("ocr", "03  LOCAL OCR\nPP-OCRv5 + bbox\nP95 ≤ 450ms")
            client_row.node(
                "quality",
                "04  QUALITY GATE\n置信度 ≥ 0.90\n低分进入 OCR 回退",
                fillcolor=WHITE,
            )
            client_row.node("classify", "05  EXTRACT\nbbox 颜色采样\n频道分类 + 新增行")

        client.edge("capture", "delta")
        client.edge("delta", "ocr")
        client.edge("ocr", "quality")
        client.edge("quality", "classify")

    with graph.subgraph(name="cluster_gateway") as gateway:
        gateway.attr(
            label="B  /  CACHE & TRANSLATE  /  缓存与中心翻译",
            labeljust="l",
            fontsize="12",
            color=BLACK,
            bgcolor=WHITE,
            fontcolor=BLACK,
            style="rounded",
            penwidth="1.2",
            margin="14",
        )
        with gateway.subgraph() as gateway_row:
            gateway_row.attr(rank="same")
            gateway_row.node(
                "render",
                "10  OVERLAY\n原位覆盖译文\n端到端 P95 ≤ 2s",
                fillcolor=BLACK,
                fontcolor=WHITE,
            )
            gateway_row.node("gpu", "09  GPU TRANSLATE\n动态批处理 ≤ 20\nP95 ≤ 650ms")
            gateway_row.node(
                "redis",
                "08  REDIS\n全局缓存 + 请求合并\n< 10ms",
                fillcolor=BLACK,
                fontcolor=WHITE,
            )
            gateway_row.node("api", "07  API GATEWAY\n认证 + 限流\nDeadline 传播")
            gateway_row.node(
                "local_cache",
                "06  LOCAL CACHE\n词典 + SQLite\n命中即返回 < 10ms",
                fillcolor=BLACK,
                fontcolor=WHITE,
            )

        gateway.edge("render", "gpu", style="invis", weight="100")
        gateway.edge("gpu", "redis", style="invis", weight="100")
        gateway.edge("redis", "api", style="invis", weight="100")
        gateway.edge("api", "local_cache", style="invis", weight="100")
        gateway.edge("local_cache", "api", constraint="false")
        gateway.edge("api", "redis", constraint="false")
        gateway.edge("redis", "gpu", constraint="false")
        gateway.edge("gpu", "render", constraint="false")

    with graph.subgraph(name="cluster_guardrail") as guardrail:
        guardrail.attr(
            label="C  /  GUARDRAILS  /  回退与可观测性（不阻塞首屏）",
            labeljust="l",
            fontsize="11",
            color=BLACK,
            bgcolor=WHITE,
            fontcolor=BLACK,
            style="rounded",
            penwidth="1.2",
            margin="14",
        )
        with guardrail.subgraph() as guardrail_row:
            guardrail_row.attr(rank="same")
            guardrail_row.node(
                "glm",
                "FROM 04  /  OCR FALLBACK\nGLM-OCR ≤ 700ms\n成功后进入步骤 05",
                fillcolor=WHITE,
                width="3.68",
            )
            guardrail_row.node(
                "metrics",
                "FROM 07  /  OBSERVE\nP50 · P95 · P99 · 429\nCER · bbox IoU",
                fillcolor=BLACK,
                fontcolor=WHITE,
                width="3.68",
            )
            guardrail_row.node(
                "deepseek",
                "FROM 10  /  ASYNC REFINE\nDeepSeek V4 Flash\n下一帧修正 · thinking off",
                fillcolor=WHITE,
                width="3.68",
            )

    graph.edge(
        "classify",
        "local_cache",
        tailport="s",
        headport="n",
        ltail="cluster_client",
        lhead="cluster_gateway",
    )
    graph.edge("render", "glm", style="invis", weight="100")
    return graph


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    output_dir = project_root / "docs" / "architecture"
    output_dir.mkdir(parents=True, exist_ok=True)

    graph = build_graph()
    dot_path = output_dir / "translation_route.dot"
    graph.save(filename=str(dot_path))
    for output_format in ("svg", "png"):
        graph.render(
            filename="translation_route",
            directory=str(output_dir),
            format=output_format,
            cleanup=True,
        )
        print(output_dir / f"translation_route.{output_format}")


if __name__ == "__main__":
    main()
