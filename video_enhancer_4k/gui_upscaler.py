import gradio as gr
import subprocess
import os
from pathlib import Path
import logging

# Configuración básica
BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "tools" / "upscaling" / "scripts"
VENV_MAIN = BASE_DIR / ".venv" / "Scripts" / "python.exe"
NCNN_BIN = BASE_DIR / "bin" / "realesrgan-ncnn-vulkan.exe"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def run_upscale(input_file, scale, mode):
    if not input_file:
        return "Error: Por favor selecciona un archivo."
    
    input_path = Path(input_file)
    ext = input_path.suffix.lower()
    
    # Determinar si es foto o video
    is_video = ext in {".mp4", ".mkv", ".avi", ".mov", ".webm"}
    is_photo = ext in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
    
    if not is_video and not is_photo:
        return f"Error: Formato {ext} no soportado."

    output_dir = BASE_DIR / "salida_upscaling"
    output_dir.mkdir(exist_ok=True)
    
    try:
        if is_photo:
            # Upscaling de fotos vía NCNN (Más robusto y ligero)
            if not NCNN_BIN.exists():
                return "Error: No se encontró el binario NCNN en bin/."
            
            output_name = input_path.stem + f"_upscaled_{scale}x" + input_path.suffix
            final_output = output_dir / output_name
            
            cmd = [
                str(NCNN_BIN),
                "-i", str(input_path),
                "-o", str(final_output),
                "-s", str(scale),
                "-n", "realesrgan-x4plus" if scale == 4 else "realesrgan-x4plus" # x2 uses same model usually but -s handles it
            ]
            
        else:
            # Upscaling de video
            output_name = input_path.stem + f"_4k.mp4"
            final_output = output_dir / output_name
            
            if mode == "IA (Máxima calidad)":
                # Video con IA (Usa el script wrapper que ya sabe manejar frames)
                cmd = [
                    str(VENV_MAIN),
                    str(SCRIPTS_DIR / "upscale_video_ai.py"),
                    "-i", str(input_path),
                    "-o", str(final_output),
                    "-s", str(scale)
                ]
            else:
                # Video Rápido (FFmpeg)
                cmd = [
                    str(VENV_MAIN),
                    str(SCRIPTS_DIR / "upscale_video_fast.py"),
                    "-i", str(input_path),
                    "-o", str(final_output),
                    "--preset", "4k",
                    "--sharpen"
                ]

        logging.info(f"Ejecutando: {' '.join(cmd)}")
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode == 0:
            if final_output.exists():
                return f"✅ ¡Éxito! Archivo guardado en: {final_output}"
            else:
                return f"✅ Proceso completado.\nInfo: {process.stdout}"
        else:
            return f"❌ Error en el proceso:\n{process.stderr}\n\nSalida:\n{process.stdout}"

    except Exception as e:
        return f"❌ Excepción inesperada: {str(e)}"

# Interfaz Gradio
with gr.Blocks(title="Antigravity — Upscaling Hub", theme=gr.themes.Soft(primary_hue="cyan")) as demo:
    gr.Markdown("""
    # 🎬 Antigravity — Upscaling Hub
    Mejora tus fotos y videos usando Inteligencia Artificial o algoritmos rápidos.
    """)
    
    with gr.Row():
        with gr.Column():
            input_file = gr.File(label="Selecciona tu video o foto", file_types=["video", "image"])
            scale = gr.Radio(choices=[2, 4], label="Factor de Escala", value=4)
            mode = gr.Dropdown(
                choices=["IA (Máxima calidad)", "Rápido (Algoritmo FFmpeg)"], 
                label="Modo (Solo para Video)", 
                value="IA (Máxima calidad)"
            )
            btn = gr.Button("🚀 Iniciar Procesamiento", variant="primary")
            
        with gr.Column():
            output_text = gr.Textbox(label="Estado del Proceso", interactive=False)
            gr.Markdown("""
            ### 💡 Información de Motores:
            - **Video IA:** Usa Real-ESRGAN NCNN. Muy lento en CPU (~1 fps) pero excelente.
            - **Video Rápido:** Usa FFmpeg Lanczos + Sharpen. Muy rápido, ideal para clips largos.
            - **Fotos:** Siempre usa el motor de IA optimizado (Python 3.9).
            """)

    btn.click(run_upscale, inputs=[input_file, scale, mode], outputs=output_text)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
