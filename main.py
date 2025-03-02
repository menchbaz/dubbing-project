import gradio as gr
import os
import shutil
import subprocess
import pysrt
import edge_tts
import asyncio
from pydub import AudioSegment

# تعریف فانکشن‌های اصلی

def setup_environment():
    """
    تنظیمات اولیه محیط کار.
    """
    if os.path.exists('input_video.mp4'):
        os.remove('input_video.mp4')
    if os.path.exists('audio.wav'):
        os.remove('audio.wav')
    if os.path.exists('audio.srt'):
        os.remove('audio.srt')
    if os.path.exists('dubbing_project'):
        shutil.rmtree('dubbing_project')
    os.makedirs('dubbing_project/dubbed_segments', exist_ok=True)

def upload_video(video_file):
    """
    آپلود ویدئو و استخراج صدا.
    """
    video_path = "input_video.mp4"
    audio_path = "audio.wav"
    
    with open(video_path, "wb") as f:
        f.write(video_file.read())
    
    # استخراج صدا از ویدئو
    subprocess.run(["ffmpeg", "-i", video_path, "-vn", audio_path])
    return "ویدئو و فایل صوتی با موفقیت آپلود شد."

def extract_text_from_audio(audio_file=None):
    """
    استخراج متن از فایل صوتی یا آپلود فایل زیرنویس.
    """
    if audio_file:
        audio_path = "audio.wav"
        with open(audio_path, "wb") as f:
            f.write(audio_file.read())
        
        # استفاده از Whisper برای استخراج متن
        subprocess.run(["whisper", audio_path, "--model", "large", "--output_dir", "./", "--output_format", "srt"])
        os.rename("audio.srt", "audio.srt")
        return "متن از فایل صوتی استخراج شد."
    else:
        return "لطفاً فایل صوتی را آپلود کنید."

def translate_subtitles(source_language, target_language, api_key=None):
    """
    ترجمه زیرنویس با استفاده از API هوش مصنوعی.
    """
    if not api_key:
        return "لطفاً کلید API خود را وارد کنید."
    
    input_subtitle_path = "audio.srt"
    output_subtitle_path = "audio_fa.srt"

    subs = pysrt.open(input_subtitle_path)
    translated_subs = []

    for sub in subs:
        # تنظیم پرامپت برای ترجمه
        prompt = f"Translate to {target_language}: {sub.text}"
        response = call_translation_api(prompt, api_key)
        translated_subs.append(response)

    # ذخیره فایل زیرنویس ترجمه شده
    for i, sub in enumerate(translated_subs):
        subs[i].text = sub
    subs.save(output_subtitle_path, encoding='utf-8')

    return "زیرنویس با موفقیت ترجمه شد."

def call_translation_api(prompt, api_key):
    """
    فراخوانی API برای ترجمه.
    """
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    return response.text

async def generate_dubbed_audio(voice_choice):
    """
    تولید صدا دوبله شده با Edge TTS.
    """
    subs = pysrt.open("audio_fa.srt")
    voice_map = {
        "فرید (FA)": "fa-IR-FaridNeural",
        "دلارا (FA)": "fa-IR-DilaraNeural",
        "Jenny (EN)": "en-US-JennyNeural",
        "Guy (EN)": "en-US-GuyNeural",
        "Katja (DE)": "de-DE-KatjaNeural",
        "Conrad (DE)": "de-DE-ConradNeural",
        "Denise (FR)": "fr-FR-DeniseNeural",
        "Henri (FR)": "fr-FR-HenriNeural",
    }
    selected_voice = voice_map.get(voice_choice)

    for i, sub in enumerate(subs):
        start_time = sub.start.seconds + sub.start.milliseconds / 1000
        end_time = sub.end.seconds + sub.end.milliseconds / 1000
        target_duration = end_time - start_time

        # تولید صدا با Edge TTS
        communicate = edge_tts.Communicate(sub.text, selected_voice)
        await communicate.save(f"dubbing_project/dubbed_segments/temp_{i+1}.mp3")

        # تبدیل به WAV
        subprocess.run([
            "ffmpeg", "-i", f"dubbing_project/dubbed_segments/temp_{i+1}.mp3",
            "-y", f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav"
        ])

        # محاسبه مدت زمان اصلی
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav"
        ], capture_output=True, text=True)
        original_duration = float(result.stdout.strip())

        # تنظیم ضریب سرعت
        speed_factor = original_duration / target_duration
        subprocess.run([
            "ffmpeg", "-i", f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav",
            "-filter:a", f"rubberband=tempo={speed_factor}",
            "-y", f"dubbing_project/dubbed_segments/dub_{i+1}.wav"
        ])

        # پاکسازی فایل‌های موقت
        os.remove(f"dubbing_project/dubbed_segments/temp_{i+1}.mp3")
        os.remove(f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav")

    return "صدا دوبله شده با موفقیت تولید شد."

def combine_audio_with_video(keep_original_audio, original_audio_volume, voice_choice):
    """
    ترکیب صدا و ویدئو با زمان‌بندی دقیق.
    """
    input_video = "input_video.mp4"
    output_video = f"final_dubbed_video_{voice_choice.split('(')[1].split(')')[0]}.mp4"
    subs = pysrt.open("audio_fa.srt")
    valid_segments = []

    filter_complex = "[0:a]volume=0[original_audio];" if not keep_original_audio else f"[0:a]volume={original_audio_volume}[original_audio];"

    for i, sub in enumerate(subs):
        start_time_ms = (sub.start.hours * 3600 + sub.start.minutes * 60 + sub.start.seconds) * 1000 + sub.start.milliseconds
        filter_complex += f"[{i+1}:a]adelay={start_time_ms}|{start_time_ms}[a{i+1}];"
        valid_segments.append(i)

    merge_command = "[original_audio]"
    for i in valid_segments:
        merge_command += f"[a{i+1}]"
    merge_command += f"amix=inputs={len(valid_segments)+1}:normalize=0[aout]"
    filter_complex += merge_command

    input_files = " ".join([f"-i dubbing_project/dubbed_segments/dub_{i+1}.wav" for i in valid_segments])

    command = f'ffmpeg -y -i {input_video} {input_files} -filter_complex "{filter_complex}" -map 0:v -map "[aout]" -c:v copy {output_video}'
    subprocess.run(command, shell=True)

    return f"ویدئو دوبله شده با موفقیت ساخته شد: {output_video}"

# تعریف واسط کاربری Gradio

with gr.Blocks() as demo:
    gr.Markdown("# دوبله کننده ویدئویی")
    
    with gr.Tab("آپلود ویدئو"):
        video_input = gr.File(label="آپلود ویدئو")
        video_upload_button = gr.Button("آپلود")
        video_output = gr.Textbox(label="نتیجه")
        video_upload_button.click(upload_video, inputs=video_input, outputs=video_output)

    with gr.Tab("استخراج متن"):
        audio_input = gr.File(label="آپلود فایل صوتی (اختیاری)")
        extract_button = gr.Button("استخراج متن")
        extract_output = gr.Textbox(label="نتیجه")
        extract_button.click(extract_text_from_audio, inputs=audio_input, outputs=extract_output)

    with gr.Tab("ترجمه زیرنویس"):
        source_lang = gr.Dropdown(["English (EN)", "Persian (FA)"], label="زبان منبع")
        target_lang = gr.Dropdown(["Persian (FA)", "English (EN)"], label="زبان هدف")
        api_key_input = gr.Textbox(label="API Key")
        translate_button = gr.Button("ترجمه")
        translate_output = gr.Textbox(label="نتیجه")
        translate_button.click(translate_subtitles, inputs=[source_lang, target_lang, api_key_input], outputs=translate_output)

    with gr.Tab("تولید صدا دوبله شده"):
        voice_choice = gr.Dropdown(list(edge_tts.VOICES.keys()), label="انتخاب صدای دوبله")
        generate_button = gr.Button("تولید صدا")
        generate_output = gr.Textbox(label="نتیجه")
        generate_button.click(lambda x: asyncio.run(generate_dubbed_audio(x)), inputs=voice_choice, outputs=generate_output)

    with gr.Tab("ترکیب صدا و ویدئو"):
        keep_audio = gr.Checkbox(label="حافظه صدای اصلی")
        audio_volume = gr.Slider(minimum=0, maximum=1, step=0.01, label="حجم صدای اصلی")
        combine_button = gr.Button("ترکیب")
        combine_output = gr.Textbox(label="نتیجه")
        combine_button.click(combine_audio_with_video, inputs=[keep_audio, audio_volume, voice_choice], outputs=combine_output)

demo.launch(share=True)
