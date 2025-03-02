import base64
import os
import shutil
import subprocess
import asyncio
import pysrt
from tqdm import tqdm
import time
from tenacity import retry, stop_after_attempt, wait_exponential
import edge_tts
import yt_dlp
import gradio as gr

# تابع پاکسازی فایل‌های قبلی
def cleanup_previous_files():
    files_to_remove = ['input_video.mp4', 'audio.wav', 'audio.srt', 'audio_fa.srt']
    for file in files_to_remove:
        if os.path.exists(file):
            os.remove(file)
    if os.path.exists('dubbing_project'):
        shutil.rmtree('dubbing_project')
    return "فایل‌های قبلی پاک شدند."

# تابع آپلود ویدیو
def upload_video(upload_method, yt_link, uploaded_file):
    cleanup_previous_files()
    
    if upload_method == "یوتیوب" and yt_link.strip():
        video_opts = {'format': 'best', 'outtmpl': 'input_video.mp4'}
        audio_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
            'outtmpl': 'audio'
        }
        with yt_dlp.YoutubeDL(video_opts) as ydl:
            ydl.download([yt_link])
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            ydl.download([yt_link])
        return "ویدیو و صوت از یوتیوب دانلود شدند."
    
    elif upload_method == "حافظه داخلی" and uploaded_file is not None:
        with open('input_video.mp4', 'wb') as f:
            f.write(uploaded_file.read())
        subprocess.run(['ffmpeg', '-i', 'input_video.mp4', '-vn', 'audio.wav'])
        return "ویدیو آپلود و صوت استخراج شد."
    
    return "لطفاً یک روش آپلود معتبر انتخاب کنید."

# تابع استخراج متن
def extract_text(extraction_method, uploaded_subtitle):
    if extraction_method == "Whisper":
        if os.path.exists('audio.wav'):
            subprocess.run(['whisper', 'audio.wav', '--model', 'large', '--output_dir', './', '--output_format', 'srt'])
            if os.path.exists('audio.srt'):
                return "متن با Whisper استخراج شد."
            return "خطا در استخراج متن با Whisper."
        return "فایل صوتی پیدا نشد. ابتدا ویدیو آپلود کنید."
    
    elif extraction_method == "آپلود زیرنویس" and uploaded_subtitle is not None:
        with open('audio.srt', 'wb') as f:
            f.write(uploaded_subtitle.read())
        return "زیرنویس آپلود شد."
    
    return "لطفاً یک روش استخراج معتبر انتخاب کنید."

# تابع ترجمه زیرنویس
def translate_subtitles(translation_method, source_lang, target_lang, api_key, uploaded_translated_sub):
    language_map = {
        "English (EN)": "English", "Persian (FA)": "فارسی", "German (DE)": "German",
        "French (FR)": "French", "Italian (IT)": "Italian", "Spanish (ES)": "Spanish",
        "Chinese (ZH)": "Chinese", "Korean (KO)": "Korean", "Russian (RU)": "Russian",
        "Arabic (AR)": "Arabic", "Japanese (JA)": "Japanese"
    }
    
    if translation_method == "هوش مصنوعی":
        if not api_key:
            return "لطفاً کلید API را وارد کنید."
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
        def translate_with_retry(text):
            model = genai.GenerativeModel('gemini-1.5-flash')
            target_lang_name = language_map.get(target_lang, "English")
            prompt = f"""Instruction:
            1. Please translate the text to {target_lang_name} with the same tone
            2. Use appropriate punctuation where necessary
            3. No additional explanation or text
            Text to translate:
            {text}"""
            if target_lang == "Persian (FA)":
                prompt = f"""دستورالعمل:
                1. فقط متن را به فارسی عامیانه و لحن خودمونی ترجمه کن
                2. هرجا لازمه از نقطه و کاما و علائم نگارشی استفاده کن
                3. اضافه گویی در ترجمه ممنوع
                متن برای ترجمه:
                {text}"""
            response = model.generate_content(prompt)
            time.sleep(3)
            return response.text
        
        subs = pysrt.open('audio.srt')
        for sub in tqdm(subs, desc="ترجمه زیرنویس"):
            sub.text = translate_with_retry(sub.text)
        subs.save('audio_fa.srt', encoding='utf-8')
        return f"ترجمه از {source_lang} به {target_lang} انجام شد."
    
    elif translation_method == "آپلود زیرنویس بصورت دستی" and uploaded_translated_sub is not None:
        with open('audio_fa.srt', 'wb') as f:
            f.write(uploaded_translated_sub.read())
        return "زیرنویس ترجمه‌شده آپلود شد."
    
    return "لطفاً یک روش ترجمه معتبر انتخاب کنید."

# تابع تولید سگمنت‌های صوتی
async def generate_audio_segments(voice_choice):
    os.makedirs('dubbing_project/dubbed_segments', exist_ok=True)
    
    VOICE_MAP = {
        "فرید (FA)": "fa-IR-FaridNeural", "دلارا (FA)": "fa-IR-DilaraNeural",
        "Jenny (EN)": "en-US-JennyNeural", "Guy (EN)": "en-US-GuyNeural",
        "Katja (DE)": "de-DE-KatjaNeural", "Conrad (DE)": "de-DE-ConradNeural",
        "Elvira (ES)": "es-ES-ElviraNeural", "Alvaro (ES)": "es-ES-AlvaroNeural",
        "Denise (FR)": "fr-FR-DeniseNeural", "Henri (FR)": "fr-FR-HenriNeural",
        "Nanami (JA)": "ja-JP-NanamiNeural", "Keita (JA)": "ja-JP-KeitaNeural",
        "SunHi (KO)": "ko-KR-SunHiNeural", "InJoon (KO)": "ko-KR-InJoonNeural",
        "Xiaoxiao (ZH)": "zh-CN-XiaoxiaoNeural", "Yunyang (ZH)": "zh-CN-YunyangNeural",
        "Svetlana (RU)": "ru-RU-SvetlanaNeural", "Dmitry (RU)": "ru-RU-DmitryNeural",
        "Amina (AR)": "ar-EG-AminaNeural", "Hamed (AR)": "ar-EG-HamedNeural",
        "Isabella (IT)": "it-IT-IsabellaNeural", "Diego (IT)": "it-IT-DiegoNeural"
    }
    
    selected_voice = VOICE_MAP.get(voice_choice)
    if not selected_voice:
        return f"گوینده {voice_choice} معتبر نیست."
    
    subs = pysrt.open('audio_fa.srt')
    for i, sub in enumerate(subs):
        start_time = sub.start.seconds + sub.start.milliseconds / 1000
        end_time = sub.end.seconds + sub.end.milliseconds / 1000
        target_duration = end_time - start_time
        
        communicate = edge_tts.Communicate(sub.text, selected_voice)
        await communicate.save(f"dubbing_project/dubbed_segments/temp_{i+1}.mp3")
        
        subprocess.run(['ffmpeg', '-i', f"dubbing_project/dubbed_segments/temp_{i+1}.mp3', '-y', f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav"])
        
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav"], capture_output=True, text=True)
        original_duration = float(result.stdout.strip())
        
        speed_factor = original_duration / target_duration
        subprocess.run(['ffmpeg', '-i', f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav', '-filter:a', f'rubberband=tempo={speed_factor}', '-y', f"dubbing_project/dubbed_segments/dub_{i+1}.wav"])
        
        os.remove(f"dubbing_project/dubbed_segments/temp_{i+1}.mp3")
        os.remove(f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav")
    
    return f"سگمنت‌های صوتی با صدای {voice_choice} ساخته شدند."

# تابع رابط برای اجرای تابع async
def generate_audio_segments_sync(voice_choice):
    asyncio.run(generate_audio_segments(voice_choice))
    return f"سگمنت‌های صوتی با صدای {voice_choice} ساخته شدند."

# تابع ترکیب ویدیو و صدا
def combine_video_audio(voice_choice, keep_original_audio, original_audio_volume):
    if not os.path.exists('input_video.mp4'):
        return "ویدیوی ورودی پیدا نشد."
    
    subs = pysrt.open('audio_fa.srt')
    filter_complex = "[0:a]volume=0[original_audio];" if not keep_original_audio else f"[0:a]volume={original_audio_volume}[original_audio];"
    
    valid_segments = []
    for i, sub in enumerate(subs):
        start_time_ms = (sub.start.hours * 3600 + sub.start.minutes * 60 + sub.start.seconds) * 1000 + sub.start.milliseconds
        filter_complex += f"[{i+1}:a]adelay={start_time_ms}|{start_time_ms}[a{i+1}];"
        valid_segments.append(i)
    
    merge_command = "[original_audio]" + "".join([f"[a{i+1}]" for i in valid_segments]) + f"amix=inputs={len(valid_segments) + 1}:normalize=0[aout]"
    filter_complex += merge_command
    
    input_files = " ".join([f"-i dubbing_project/dubbed_segments/dub_{i+1}.wav" for i in valid_segments])
    voice_code = voice_choice.split("(")[1].split(")")[0] if "(" in voice_choice else "FA"
    output_filename = f'final_dubbed_video_{voice_code}.mp4'
    
    command = f'ffmpeg -y -i input_video.mp4 {input_files} -filter_complex "{filter_complex}" -map 0:v -map "[aout]" -c:v copy {output_filename}'
    subprocess.run(command, shell=True)
    
    if os.path.exists(output_filename):
        return output_filename, f"ویدیو با صدای {voice_choice} ساخته شد."
    return None, "خطا در ساخت ویدیو."

# رابط کاربری Gradio
with gr.Blocks(title="Dubbing Tool") as demo:
    gr.Markdown("## ابزار دوبله ویدیو")
    
    with gr.Tab("آپلود ویدیو"):
        upload_method = gr.Radio(["یوتیوب", "حافظه داخلی"], label="روش آپلود")
        yt_link = gr.Textbox(label="لینک یوتیوب (در صورت انتخاب یوتیوب)")
        uploaded_file = gr.File(label="آپلود فایل ویدیویی (در صورت انتخاب حافظه داخلی)")
        upload_btn = gr.Button("آپلود")
        upload_output = gr.Textbox(label="نتیجه")
        upload_btn.click(upload_video, inputs=[upload_method, yt_link, uploaded_file], outputs=upload_output)
    
    with gr.Tab("استخراج متن"):
        extraction_method = gr.Radio(["Whisper", "آپلود زیرنویس"], label="روش استخراج")
        uploaded_subtitle = gr.File(label="آپلود فایل زیرنویس (در صورت انتخاب آپلود)")
        extract_btn = gr.Button("استخراج")
        extract_output = gr.Textbox(label="نتیجه")
        extract_btn.click(extract_text, inputs=[extraction_method, uploaded_subtitle], outputs=extract_output)
    
    with gr.Tab("ترجمه زیرنویس"):
        translation_method = gr.Radio(["هوش مصنوعی", "آپلود زیرنویس بصورت دستی"], label="روش ترجمه")
        source_lang = gr.Dropdown(["English (EN)", "Persian (FA)", "German (DE)", "French (FR)", "Italian (IT)", "Spanish (ES)", "Chinese (ZH)", "Korean (KO)", "Russian (RU)", "Arabic (AR)", "Japanese (JA)"], label="زبان مبدا", value="English (EN)")
        target_lang = gr.Dropdown(["Persian (FA)", "English (EN)", "German (DE)", "French (FR)", "Italian (IT)", "Spanish (ES)", "Chinese (ZH)", "Korean (KO)", "Russian (RU)", "Arabic (AR)", "Japanese (JA)"], label="زبان مقصد", value="Persian (FA)")
        api_key = gr.Textbox(label="کلید API گوگل (در صورت انتخاب هوش مصنوعی)", type="password")
        uploaded_translated_sub = gr.File(label="آپلود زیرنویس ترجمه‌شده (در صورت انتخاب دستی)")
        translate_btn = gr.Button("ترجمه")
        translate_output = gr.Textbox(label="نتیجه")
        translate_btn.click(translate_subtitles, inputs=[translation_method, source_lang, target_lang, api_key, uploaded_translated_sub], outputs=translate_output)
    
    with gr.Tab("تولید سگمنت‌های صوتی"):
        voice_choice = gr.Dropdown(list(VOICE_MAP.keys()), label="انتخاب گوینده", value="فرید (FA)")
        generate_btn = gr.Button("تولید")
        generate_output = gr.Textbox(label="نتیجه")
        generate_btn.click(generate_audio_segments_sync, inputs=[voice_choice], outputs=generate_output)
    
    with gr.Tab("ترکیب ویدیو و صدا"):
        keep_original_audio = gr.Checkbox(label="حفظ صدای اصلی ویدیو", value=False)
        original_audio_volume = gr.Slider(0, 1, value=0.05, step=0.005, label="میزان صدای اصلی (در صورت فعال بودن)")
        combine_btn = gr.Button("ترکیب")
        combine_output_file = gr.File(label="دانلود ویدیوی نهایی")
        combine_output_text = gr.Textbox(label="نتیجه")
        combine_btn.click(combine_video_audio, inputs=[voice_choice, keep_original_audio, original_audio_volume], outputs=[combine_output_file, combine_output_text])

demo.launch()
