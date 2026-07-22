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
        pad="0.35",
        nodesep="0.30",
        ranksep="0.62",
        splines="ortho",
        newrank="true",
        compound="true",
        dpi="180",
        fontname="Microsoft YaHei",
        label="20 人并发 · 端到端 P95 ≤ 2s",
        labelloc="t",
        fontsize="24",
        fontcolor=BLACK,
    )
    graph.attr(
        "node",
        shape="box",
        style="rounded,filled",
        color=BLACK,
        fillcolor=YELLOW,
        fontcolor=BLACK,
        fontname="Microsoft YaHei",
        fontsize="11",
        margin="0.16,0.12",
        penwidth="1.8",
    )
    graph.attr(
        "edge",
        color=BLACK,
        fontcolor=BLACK,
        fontname="Microsoft YaHei",
        fontsize="9",
        penwidth="1.8",
        arrowsize="0.75",
    )

    with graph.subgraph(name="cluster_client") as client:
        client.attr(
            label="客户端本地链路 · 每个用户独立执行",
            color=BLACK,
            bgcolor=WHITE,
            fontcolor=BLACK,
            style="rounded",
            penwidth="2",
            margin="18",
        )
        with client.subgraph() as client_row:
            client_row.attr(rank="same")
            client_row.node(
                "users",
                "20 个并发客户端\n同步突发触发",
                fillcolor=BLACK,
                fontcolor=WHITE,
            )
            client_row.node("capture", "01  截图 + 立即模糊\n预算 ≤ 50ms")
            client_row.node(
                "delta",
                "02  感知哈希 + 行差异\n未变化：复用可信结果",
                fillcolor=WHITE,
            )
            client_row.node("ocr", "03  本地 PP-OCRv5\n文本 + bbox\nP95 ≤ 450ms")
            client_row.node(
                "quality",
                "04  OCR 质量门控\n置信度 ≥ 0.90",
                fillcolor=WHITE,
            )
            client_row.node("classify", "05  bbox 颜色采样\n频道分类 + 新增行提取")

        client.edge("users", "capture")
        client.edge("capture", "delta")
        client.edge("delta", "ocr")
        client.edge("ocr", "quality")
        client.edge("quality", "classify")

    with graph.subgraph(name="cluster_gateway") as gateway:
        gateway.attr(
            label="缓存与中心翻译链路 · 仅发送新增文本",
            color=BLACK,
            bgcolor=WHITE,
            fontcolor=BLACK,
            style="rounded",
            penwidth="2",
            margin="18",
        )
        with gateway.subgraph() as gateway_row:
            gateway_row.attr(rank="same")
            gateway_row.node(
                "local_cache",
                "06  本地词典 / SQLite\n命中即返回 < 10ms",
                fillcolor=BLACK,
                fontcolor=WHITE,
            )
            gateway_row.node("api", "07  FastAPI 网关\n认证 · 限流 · Deadline")
            gateway_row.node(
                "redis",
                "08  Redis 全局缓存\n请求合并 < 10ms",
                fillcolor=BLACK,
                fontcolor=WHITE,
            )
            gateway_row.node("gpu", "09  GPU 本地翻译\n动态批处理 ≤ 20\nP95 ≤ 650ms")
            gateway_row.node(
                "render",
                "10  原位覆盖译文\n端到端 P95 ≤ 2s",
                fillcolor=BLACK,
                fontcolor=WHITE,
            )

        gateway.edge("local_cache", "api")
        gateway.edge("api", "redis")
        gateway.edge("redis", "gpu")
        gateway.edge("gpu", "render")

    with graph.subgraph(name="cluster_guardrail") as guardrail:
        guardrail.attr(
            label="质量回退与可观测性 · 不阻塞首屏",
            color=BLACK,
            bgcolor=WHITE,
            fontcolor=BLACK,
            style="rounded,dashed",
            penwidth="1.6",
            margin="16",
        )
        with guardrail.subgraph() as guardrail_row:
            guardrail_row.attr(rank="same")
            guardrail_row.node(
                "glm",
                "OCR 低置信度\nGLM-OCR 回退 ≤ 700ms\n成功后进入步骤 05",
                fillcolor=WHITE,
            )
            guardrail_row.node(
                "metrics",
                "Prometheus / Grafana\nP50 · P95 · P99\n429 · CER · bbox IoU",
                fillcolor=BLACK,
                fontcolor=WHITE,
            )
            guardrail_row.node(
                "deepseek",
                "翻译低置信度\nDeepSeek V4 Flash 异步纠错\n下一帧修正 · thinking=disabled",
                fillcolor=WHITE,
            )

    graph.edge("classify", "local_cache", ltail="cluster_client", lhead="cluster_gateway")
    graph.edge("quality", "glm", style="dashed", constraint="false")
    graph.edge("api", "metrics", style="dashed")
    graph.edge("render", "deepseek", style="dashed")
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
