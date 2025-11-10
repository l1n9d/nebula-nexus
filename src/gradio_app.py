import json
import logging
from typing import Iterator

import gradio as gr
import httpx

logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_MODEL = "llama3.2:1b"
AVAILABLE_CATEGORIES = ["cs.AI", "cs.LG"]


async def stream_response(
    query: str, top_k: int = 3, use_hybrid: bool = True, model: str = DEFAULT_MODEL, categories: str = ""
) -> Iterator[str]:
    """Stream response from the RAG API"""
    if not query.strip():
        yield "### ⚠️ Empty Query\n\n Please enter a question to get started!"
        return

    # Parse categories
    category_list = [cat.strip() for cat in categories.split(",") if cat.strip()] if categories else None

    # Prepare request payload
    payload = {"query": query, "top_k": top_k, "use_hybrid": use_hybrid, "model": model, "categories": category_list}

    try:
        url = f"{API_BASE_URL}/stream"
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload, headers={"Accept": "text/plain"}) as response:
                if response.status_code != 200:
                    yield f"### ❌ API Error\n\nServer returned status `{response.status_code}`\n\n💡 *Please check if the API server is running.*"
                    return

                current_answer = ""
                sources = []
                chunks_used = 0
                search_mode = ""

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        try:
                            data = json.loads(data_str)

                            # Handle error
                            if "error" in data:
                                yield f"### ❌ Error\n\n{data['error']}\n\n💡 *Please try again or adjust your query.*"
                                return

                            # Handle metadata
                            if "sources" in data:
                                sources = data["sources"]
                                chunks_used = data.get("chunks_used", 0)
                                search_mode = data.get("search_mode", "unknown")
                                continue

                            # Handle streaming chunks
                            if "chunk" in data:
                                current_answer += data["chunk"]
                                # Format response with sources if we have them
                                formatted_response = f"### 🤖 AI Answer\n\n{current_answer}"
                                if sources or chunks_used:
                                    formatted_response += f"\n\n---\n\n"
                                    formatted_response += f"### 📊 Search Insights\n\n"
                                    formatted_response += f"**Search Mode:** `{search_mode}`  \n"
                                    formatted_response += f"**Chunks Retrieved:** `{chunks_used}`  \n"
                                    if sources:
                                        formatted_response += f"**Papers Analyzed:** `{len(sources)}`\n\n"
                                        formatted_response += "#### 📚 Top Sources:\n\n"
                                        for i, source in enumerate(sources[:3], 1):  # Show first 3 sources
                                            paper_id = source.split('/')[-1]
                                            formatted_response += f"{i}. 📄 [{paper_id}]({source})\n"
                                        if len(sources) > 3:
                                            formatted_response += f"\n*... and {len(sources) - 3} more papers*\n"

                                yield formatted_response

                            # Handle completion
                            if data.get("done", False):
                                final_answer = data.get("answer", current_answer)
                                if final_answer != current_answer:
                                    current_answer = final_answer

                                # Final formatted response with enhanced styling
                                formatted_response = f"### 🤖 AI Answer\n\n{current_answer}"
                                if sources or chunks_used:
                                    formatted_response += f"\n\n---\n\n"
                                    formatted_response += f"### 📊 Search Insights\n\n"
                                    formatted_response += f"**Search Mode:** `{search_mode}`  \n"
                                    formatted_response += f"**Chunks Retrieved:** `{chunks_used}`  \n"
                                    if sources:
                                        formatted_response += f"**Papers Analyzed:** `{len(sources)}`\n\n"
                                        formatted_response += "#### 📚 Top Sources:\n\n"
                                        for i, source in enumerate(sources[:3], 1):
                                            paper_id = source.split('/')[-1]
                                            formatted_response += f"{i}. 📄 [{paper_id}]({source})\n"
                                        if len(sources) > 3:
                                            formatted_response += f"\n*... and {len(sources) - 3} more papers*\n"
                                
                                formatted_response += f"\n\n✨ *Answer generated successfully!*"
                                yield formatted_response
                                break

                        except json.JSONDecodeError:
                            continue  # Skip malformed JSON lines

    except httpx.RequestError as e:
        yield f"### 🔌 Connection Error\n\n**Issue:** `{str(e)}`\n\n**API URL:** `{API_BASE_URL}`\n\n💡 *Make sure the API server is running and accessible.*"
    except Exception as e:
        yield f"### ⚠️ Unexpected Error\n\n**Details:** `{str(e)}`\n\n💡 *Please try again or contact support if the issue persists.*"


def create_gradio_interface():
    """Create and configure the Gradio interface"""

    # Custom CSS for a sleek, modern dark look
    custom_css = """
    .gradio-container {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    
    .main-header {
        text-align: center;
        padding: 2rem;
        background: rgba(30, 30, 50, 0.95) !important;
        border-radius: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        margin-bottom: 2rem;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(139, 92, 246, 0.3);
    }
    
    .main-header h1 {
        background: linear-gradient(135deg, #a78bfa 0%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }
    
    .main-header p {
        color: #d1d5db !important;
        font-size: 1.2rem;
        font-weight: 500;
    }
    
    .input-section {
        background: rgba(30, 30, 50, 0.95) !important;
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        margin-bottom: 1.5rem;
        border: 1px solid rgba(139, 92, 246, 0.3);
    }
    
    .response-box {
        background: rgba(30, 30, 50, 0.95) !important;
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        min-height: 400px;
        border: 1px solid rgba(139, 92, 246, 0.3);
    }
    
    .gr-button-primary {
        background: linear-gradient(135deg, #8b5cf6 0%, #a855f7 100%) !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        padding: 1rem 2rem !important;
        transition: transform 0.2s, box-shadow 0.2s !important;
    }
    
    .gr-button-primary:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 20px rgba(139, 92, 246, 0.5) !important;
        background: linear-gradient(135deg, #7c3aed 0%, #9333ea 100%) !important;
    }
    
    .gr-button-secondary {
        background: rgba(55, 65, 81, 0.8) !important;
        border: 1px solid rgba(139, 92, 246, 0.3) !important;
        border-radius: 12px !important;
        color: #d1d5db !important;
    }
    
    .gr-button-secondary:hover {
        background: rgba(75, 85, 99, 0.9) !important;
        border-color: rgba(139, 92, 246, 0.5) !important;
    }
    
    .gr-box {
        border-radius: 12px !important;
        border: 2px solid rgba(75, 85, 99, 0.5) !important;
        background: rgba(30, 30, 50, 0.7) !important;
    }
    
    .gr-input, .gr-dropdown, .gr-textbox {
        border-radius: 12px !important;
        border: 2px solid rgba(75, 85, 99, 0.5) !important;
        background: rgba(17, 24, 39, 0.8) !important;
        color: #e5e7eb !important;
        transition: border-color 0.2s !important;
    }
    
    .gr-input:focus, .gr-dropdown:focus, .gr-textbox:focus {
        border-color: #8b5cf6 !important;
        box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.2) !important;
    }
    
    .gr-form {
        background: rgba(30, 30, 50, 0.5) !important;
        border: 1px solid rgba(75, 85, 99, 0.3) !important;
    }
    
    label {
        color: #d1d5db !important;
        font-weight: 600 !important;
    }
    
    .gr-accordion {
        background: rgba(30, 30, 50, 0.7) !important;
        border: 1px solid rgba(75, 85, 99, 0.3) !important;
    }
    
    .example-box {
        background: rgba(30, 30, 50, 0.9) !important;
        padding: 1rem;
        border-radius: 12px;
        margin: 0.5rem;
        cursor: pointer;
        transition: transform 0.2s, box-shadow 0.2s;
        border: 2px solid rgba(75, 85, 99, 0.5);
        color: #d1d5db !important;
    }
    
    .example-box:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
        border-color: #8b5cf6;
    }
    
    .info-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        background: linear-gradient(135deg, #8b5cf6 0%, #a855f7 100%);
        color: white;
        border-radius: 20px;
        font-size: 0.875rem;
        font-weight: 600;
        margin: 0.25rem;
    }
    
    .footer-section {
        background: rgba(30, 30, 50, 0.9) !important;
        padding: 1.5rem;
        border-radius: 16px;
        margin-top: 2rem;
        text-align: center;
        border: 1px solid rgba(139, 92, 246, 0.3);
    }
    
    .markdown-text {
        color: #e5e7eb !important;
    }
    
    p, span, div {
        color: #d1d5db !important;
    }
    
    .gr-markdown {
        color: #e5e7eb !important;
    }
    
    .gr-markdown h1, .gr-markdown h2, .gr-markdown h3 {
        color: #c4b5fd !important;
    }
    
    .gr-markdown code {
        background: rgba(17, 24, 39, 0.8) !important;
        color: #a78bfa !important;
        padding: 0.2rem 0.4rem;
        border-radius: 4px;
    }
    
    .gr-markdown a {
        color: #a78bfa !important;
    }
    
    .gr-markdown a:hover {
        color: #c4b5fd !important;
    }
    """

    # Create custom dark theme
    custom_theme = gr.themes.Soft(
        primary_hue="purple",
        secondary_hue="indigo",
        neutral_hue="slate",
        font=["Inter", "sans-serif"],
    ).set(
        button_primary_background_fill="*primary_500",
        button_primary_background_fill_hover="*primary_600",
        button_primary_text_color="white",
        block_label_text_size="*text_lg",
        block_label_text_weight="600",
        body_background_fill="*neutral_950",
        body_text_color="*neutral_200",
        block_background_fill="*neutral_900",
        input_background_fill="*neutral_800",
    )

    with gr.Blocks(
        title="✨ Nebula Nexus - AI Research Navigator",
        theme=custom_theme,
        css=custom_css,
    ) as interface:
        
        # Header
        with gr.Row(elem_classes="main-header"):
            gr.Markdown(
                """
                # ✨ Nebula Nexus
                ### AI Research Navigator
                Explore 73,000+ arXiv Papers with Intelligent Hybrid Search powered by LLM
                """,
                elem_classes="header-content"
            )

        # Main Input Section
        with gr.Row(elem_classes="input-section"):
            with gr.Column(scale=4):
                query_input = gr.Textbox(
                    label="🔍 Ask Your Research Question",
                    placeholder="E.g., What are the latest advances in transformer architectures?",
                    lines=3,
                    max_lines=6,
                    show_label=True,
                )
            
            with gr.Column(scale=1, min_width=150):
                submit_btn = gr.Button(
                    "🚀 Ask AI",
                    variant="primary",
                    size="lg",
                    scale=1,
                )
                clear_btn = gr.Button(
                    "🗑️ Clear",
                    variant="secondary",
                    size="lg",
                    scale=1,
                )

        # Advanced Options
        with gr.Row():
            with gr.Column():
                with gr.Accordion("⚙️ Advanced Settings", open=False):
                    with gr.Row():
                        with gr.Column():
                            top_k = gr.Slider(
                                minimum=1,
                                maximum=10,
                                value=3,
                                step=1,
                                label="📊 Context Chunks",
                                info="Number of paper chunks to retrieve",
                            )
                            
                            use_hybrid = gr.Checkbox(
                                value=True,
                                label="🔀 Hybrid Search Mode",
                                info="Combine BM25 keyword + vector embeddings (recommended)",
                            )
                        
                        with gr.Column():
                            model_choice = gr.Dropdown(
                                choices=["llama3.2:1b", "llama3.2:3b", "llama3.1:8b", "qwen2.5:7b"],
                                value=DEFAULT_MODEL,
                                label="🤖 LLM Model",
                                info="Larger models = better answers but slower",
                            )
                            
                            categories = gr.Textbox(
                                label="🏷️ arXiv Categories",
                                placeholder="cs.AI, cs.LG, cs.CL",
                                info="Filter by categories (comma-separated, optional)",
                            )

        # Examples Section
        with gr.Row():
            gr.Examples(
                examples=[
                    ["What are transformers in machine learning?"],
                    ["Explain attention mechanisms in neural networks"],
                    ["Latest advances in reinforcement learning"],
                    ["How do diffusion models work?"],
                    ["Applications of graph neural networks"],
                ],
                inputs=[query_input],
                label="💡 Example Questions",
                examples_per_page=5,
            )

        # Response Section
        with gr.Row():
            with gr.Column():
                response_output = gr.Markdown(
                    label="✨ AI Response",
                    value="👋 **Ready to explore!** Ask a question above to get started.",
                    show_label=True,
                    elem_classes="response-box",
                )

        # Footer Info
        with gr.Row(elem_classes="footer-section"):
            gr.Markdown(
                """
                <div style="color: #d1d5db;">
                <p style="color: #e5e7eb;"><strong>📚 Available Categories:</strong></p>
                <span class="info-badge">cs.AI - Artificial Intelligence</span>
                <span class="info-badge">cs.LG - Machine Learning</span>
                <span class="info-badge">cs.CL - NLP</span>
                <span class="info-badge">cs.CV - Computer Vision</span>
                <span class="info-badge">cs.NE - Neural Networks</span>
                <span class="info-badge">stat.ML - Statistical ML</span>
                <br><br>
                <p style="margin-top: 1rem; font-size: 0.9rem; color: #d1d5db;">
                💡 <strong>Tip:</strong> Enable hybrid search for the best results | Use 3-5 chunks for optimal balance
                </p>
                </div>
                """
            )

        # Event Handlers
        def clear_interface():
            return "", "👋 **Ready to explore!** Ask a question above to get started."
        
        submit_btn.click(
            fn=stream_response,
            inputs=[query_input, top_k, use_hybrid, model_choice, categories],
            outputs=[response_output],
            show_progress="full",
        )

        query_input.submit(
            fn=stream_response,
            inputs=[query_input, top_k, use_hybrid, model_choice, categories],
            outputs=[response_output],
            show_progress="full",
        )
        
        clear_btn.click(
            fn=clear_interface,
            inputs=[],
            outputs=[query_input, response_output],
        )

    return interface


def main():
    """Main entry point for the Gradio app"""
    print("=" * 60)
    print("✨ Nebula Nexus - AI Research Navigator")
    print("=" * 60)
    print(f"🚀 Starting Gradio Interface...")
    print(f"📡 API Base URL: {API_BASE_URL}")
    print(f"🎨 Theme: Custom Purple Gradient")
    print(f"🌐 Server: 0.0.0.0:7860")
    print("=" * 60)

    interface = create_gradio_interface()

    # Launch the interface
    interface.launch(
        server_name="0.0.0.0",
        server_port=7860,  # Standard port for consistency with GCP
        share=False,
        show_error=True,
        quiet=False,
        favicon_path="favicon.ico",
    )


if __name__ == "__main__":
    main()
