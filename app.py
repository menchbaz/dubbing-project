import gradio as gr
import asyncio
from gradio_interface import download_youtube_video, transcribe_audio, generate_speech, merge_audio_video

def process_video(youtube_url):
    msg, video_path, audio_path = download_youtube_video(youtube_url)
    if not video_path:
        return msg, None
    
    msg_transcribe, subtitle_path = transcribe_audio()
    return msg + "\n" + msg_transcribe, subtitle_path

async def dubbing_process():
    msg_speech = await generate_speech()
    final_video = merge_audio_video()
    return msg_speech, final_video

with gr.Blocks() as app:
    gr.Markdown("## 🎙️ سیستم دوبله خودکار ویدیو")

    with gr.Row():
        youtube_url = gr.Textbox(label="لینک یوتیوب")
        process_btn = gr.Button("دانلود و پردازش ویدیو")

    subtitle_output = gr.File(label="زیرنویس استخراج شده")

    process_btn.click(process_video, inputs=[youtube_url], outputs=[gr.Textbox(), subtitle_output])

    with gr.Row():
        dub_btn = gr.Button("شروع دوبله")
        final_video_output = gr.Video(label="ویدیوی نهایی")

    dub_btn.click(dubbing_process, outputs=[gr.Textbox(), final_video_output])

app.launch(share=True)
