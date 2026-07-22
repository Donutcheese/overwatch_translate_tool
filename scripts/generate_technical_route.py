"""生成 20 并发、P95 2 秒技术路线图。"""

from pathlib import Path

from graphviz import Digraph


YELLOW = "#f4c320"
BLACK = "#2a2a2a"
WHITE = "#ffffff"


def build_graph() -> Digraph:
    graph = Digraph("ow_translation_route", comment="OW 翻译工具技术路线")
    graph.attr(
        rankdir="LR",
        bgcolor=WHITE,
        pad="0.30",
        nodesep="0.35",
        ranksep="0.55",
        splines="polyline",
        fontname="Microsoft YaHei",
        label="20 人并发 · 端到端 P95 ≤ 2s",
        labelloc="t",
        fontsize="22",
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
        fontsize="12",
        margin="0.14,0.10",
        penwidth="1.6",
    )
    graph.attr(
        "edge",
        color=BLACK,
        fontcolor=BLACK,
        fontname="Microsoft YaHei",
        fontsize="10",
        penwidth="1.6",
        arrowsize="0.75",
    )

    with graph.subgraph(name="cluster_client") as client:
        client.attr(
            label="客户端（20 实例，本地分摊 OCR）",
            color=BLACK,
            bgcolor=WHITE,
            fontcolor=BLACK,
            style="rounded",
            penwidth="2",
        )
        client.node("capture", "截图 + 立即模糊\n≤ 50ms")
        client.node("hash", "感知哈希\n画面是否变化？", shape="diamond", fillcolor=WHITE)
        client.node("ocr", "本地 PP-OCRv5 Mobile\n文本 + bbox · P95 ≤ 450ms")
        client.node("confidence", "OCR 置信度\n≥ 0.90？", shape="diamond", fillcolor=WHITE)
        client.node("classify", "bbox 颜色采样\n频道分类 + 新增行提取")
        client.node("local_cache", "本地词典 / SQLite\n热路径 < 10ms", fillcolor=BLACK, fontcolor=WHITE)
        client.node("render", "原位覆盖译文\n端到端 P95 ≤ 2s", fillcolor=BLACK, fontcolor=WHITE)

    with graph.subgraph(name="cluster_gateway") as gateway:
        gateway.attr(
            label="中心翻译网关",
            color=BLACK,
            bgcolor=WHITE,
            fontcolor=BLACK,
            style="rounded",
            penwidth="2",
        )
        gateway.node("gateway", "FastAPI\n认证 · 限流 · 100ms deadline")
        gateway.node("redis", "Redis 全局缓存\n请求合并 < 10ms", fillcolor=BLACK, fontcolor=WHITE)
        gateway.node("gpu", "GPU 本地翻译\n动态批处理 ≤ 20\nP95 ≤ 650ms")

    with graph.subgraph(name="cluster_fallback") as fallback:
        fallback.attr(
            label="非关键路径回退",
            color=BLACK,
            bgcolor=WHITE,
            fontcolor=BLACK,
            style="rounded,dashed",
            penwidth="1.6",
        )
        fallback.node("glm", "GLM-OCR 回退\n硬超时 700ms", fillcolor=WHITE)
        fallback.node("deepseek", "DeepSeek V4 Flash\n异步纠错 · thinking=disabled", fillcolor=WHITE)

    graph.node(
        "metrics",
        "Prometheus / Grafana\nP50 · P95 · P99 · 429 · 准确率",
        fillcolor=BLACK,
        fontcolor=WHITE,
    )

    graph.edge("capture", "hash")
    graph.edge("hash", "render", label="未变化 / 缓存命中")
    graph.edge("hash", "ocr", label="变化")
    graph.edge("ocr", "confidence")
    graph.edge("confidence", "classify", label="是")
    graph.edge("confidence", "glm", label="否")
    graph.edge("glm", "classify", label="成功")
    graph.edge("classify", "local_cache")
    graph.edge("local_cache", "render", label="命中")
    graph.edge("local_cache", "gateway", label="未命中")
    graph.edge("gateway", "redis")
    graph.edge("redis", "render", label="命中")
    graph.edge("redis", "gpu", label="未命中")
    graph.edge("gpu", "render", label="首屏结果")
    graph.edge("gpu", "deepseek", label="低置信度")
    graph.edge("deepseek", "render", label="后台修正", style="dashed")
    graph.edge("gateway", "metrics", style="dashed")
    graph.edge("ocr", "metrics", style="dashed")
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
