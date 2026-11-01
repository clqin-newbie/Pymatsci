css = """
.modal-overlay {
    position: fixed !important;
    inset: 0 !important;
    z-index: 9999 !important;
    background: rgba(0, 0, 0, 0.45) !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
.modal-card {
    background: var(--body-background-fill) !important;
    border: 1px solid var(--border-color-primary) !important;
    border-radius: 16px !important;
    padding: 24px !important;
    width: min(650px, 90vw) !important;
    max-height: 85vh !important;
    overflow-y: auto !important;
    box-shadow: 0 12px 40px rgba(0,0,0,.25) !important;
}
"""

def module():
    # 弹窗：默认隐藏
    with gr.Column(
        visible=False,
        elem_classes=["modal-overlay"]
    ) as modal:
        with gr.Column(elem_classes=["modal-card"]):
            gr.Markdown("## 参数设置")
            name = gr.Textbox(label="名称", value="Si")
            size = gr.Slider(
                minimum=1,
                maximum=10,
                value=3,
                label="晶胞尺寸"
            )

            with gr.Row():
                confirm = gr.Button("确认", variant="primary")
                close = gr.Button("取消")