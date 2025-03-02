import gradio as gr
import os
import base64
import yt_dlp
import pysrt
import edge_tts
import asyncio
import subprocess
from pydub import AudioSegment
from tenacity import retry, stop_after_attempt, wait_exponential

# ---------------------- توابع کمکی ----------------------

def install_dependencies():
    """نصب کتابخانه‌های مورد نیاز"""
    encoded_url = "aHR0cHM6Ly9naXRodWIuY29tL3lhcmFuYmFyemkvYWlnb2xkZW4tYXVkaW8tdG8tdGV4dC5naXQ="
    decoded_url = base64.b64decode(encoded_url.encode()).decode()
    os.system(f"pip install git+{decoded_url}")
    os.system("pip install edge_tts")
    os.system("pip install yt-dlp")
    os.system("pip install pysrt")
    os.system("pip install rubberband-cli")
    os.system("pip install pydub")
    os.system("sudo apt update && sudo apt install ffmpeg")

def clear_previous_files():
    """پاکسازی فایل‌های قبلی"""
    files_to_remove = ["input_video.mp4", "audio.wav", "audio.srt", "audio_fa.srt"]
    for file in files_to_remove:
        if os.path.exists(file):
            os.remove(file)
    if os.path.exists("dubbing_project"):
        shutil.rmtree("dubbing_project")

def process_youtube(url):
    """دانلود ویدیو و استخراج صدا از یوتیوب"""
    if url.strip():
        # دانلود ویدیو
        video_opts = {
            'format': 'best',
            'outtmpl': 'input_video.mp4'
        }
        with yt_dlp.YoutubeDL(video_opts) as ydl:
            ydl.download([url])

        # استخراج صدا
        audio_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'outtmpl': 'audio'
        }
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            ydl.download([url])
        return True
    return False

def extract_text_from_audio():
    """استخراج متن از فایل صوتی با استفاده از Whisper"""
    if os.path.exists('audio.wav'):
        os.system("whisper audio.wav --model large --output_dir ./ --output_format srt")
        os.rename("audio.srt", "audio.srt")  # اطمینان از نام فایل صحیح
    else:
        raise Exception("لطفاً ابتدا یک فایل صوتی آپلود کنید.")

def translate_subtitles(api_key, source_lang, target_lang):
    """ترجمه زیرنویس با استفاده از هوش مصنوعی"""
    genai.configure(api_key=api_key)
    filename = '/content/audio.srt'
    output_filename = '/content/audio_translated.srt'

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def translate_subtitle_with_retry(text):
        model = genai.GenerativeModel('gemini-1.5-flash', safety_settings={
            genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
            genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
        })

        language_map = {
            "Persian (FA)": "فارسی",
            "English (EN)": "English",
            "German (DE)": "German",
            "French (FR)": "French",
            "Italian (IT)": "Italian",
            "Spanish (ES)": "Spanish",
            "Chinese (ZH)": "Chinese",
            "Korean (KO)": "Korean",
            "Russian (RU)": "Russian",
            "Arabic (AR)": "Arabic",
            "Japanese (JA)": "Japanese"
        }

        target_lang_name = language_map.get(target_lang, "English")

        if target_lang == "Persian (FA)":
            prompt = f"""دستورالعمل:
            1. فقط متن را به فارسی عامیانه و لحن خودمونی ترجمه کن
            2. هرجا لازمه از نقطه و کاما و علائم نگارشی استفاده کن
            3. اضافه گویی در ترجمه ممنوع
            متن برای ترجمه:
            {text}"""
        else:
            prompt = f"""Instruction:
            1. Please translate the text to {target_lang_name} with the same tone
            2. Use appropriate punctuation where necessary
            3. No additional explanation or text
            Text to translate:
            {text}"""

        response = model.generate_content(prompt)
        time.sleep(3)
        return response.text

    subs = pysrt.open(filename)
    for i, sub in enumerate(subs):
        sub.text = translate_subtitle_with_retry(sub.text)
    subs.save(output_filename, encoding='utf-8')
    os.rename(output_filename, 'audio_fa.srt')

async def generate_speech(voice_choice):
    """تولید سگمنت‌های صوتی با زمان‌بندی دقیق"""
    subs = pysrt.open('/content/audio_fa.srt')

    VOICE_MAP = {
        "فرید (FA)": "fa-IR-FaridNeural",
        "دلارا (FA)": "fa-IR-DilaraNeural",
        "Jenny (EN)": "en-US-JennyNeural",
        "Guy (EN)": "en-US-GuyNeural",
        "Katja (DE)": "de-DE-KatjaNeural",
        "Conrad (DE)": "de-DE-ConradNeural",
        "Denise (FR)": "fr-FR-DeniseNeural",
        "Henri (FR)": "fr-FR-HenriNeural",
        "Isabella (IT)": "it-IT-IsabellaNeural",
        "Diego (IT)": "it-IT-DiegoNeural",
        "Elvira (ES)": "es-ES-ElviraNeural",
        "Alvaro (ES)": "es-ES-AlvaroNeural",
        "Xiaoxiao (ZH)": "zh-CN-XiaoxiaoNeural",
        "Yunyang (ZH)": "zh-CN-YunyangNeural",
        "SunHi (KO)": "ko-KR-SunHiNeural",
        "InJoon (KO)": "ko-KR-InJoonNeural",
        "Svetlana (RU)": "ru-RU-SvetlanaNeural",
        "Dmitry (RU)": "ru-RU-DmitryNeural",
        "Amina (AR)": "ar-EG-AminaNeural",
        "Hamed (AR)": "ar-EG-HamedNeural",
        "Nanami (JA)": "ja-JP-NanamiNeural",
        "Keita (JA)": "ja-JP-KeitaNeural"
    }

    selected_voice = VOICE_MAP.get(voice_choice)
    if not selected_voice:
        raise Exception(f"گوینده انتخاب شده '{voice_choice}' در لیست موجود نیست.")

    os.makedirs('dubbing_project/dubbed_segments', exist_ok=True)

    for i, sub in enumerate(subs):
        start_time = sub.start.seconds + sub.start.milliseconds / 1000
        end_time = sub.end.seconds + sub.end.milliseconds / 1000
        target_duration = end_time - start_time

        communicate = edge_tts.Communicate(sub.text, selected_voice)
        await communicate.save(f"dubbing_project/dubbed_segments/temp_{i+1}.mp3")

        subprocess.run([
            'ffmpeg', '-i', f"dubbing_project/dubbed_segments/temp_{i+1}.mp3",
            '-y', f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav"
        ])

        result = subprocess.run([
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav"
        ], capture_output=True, text=True)

        original_duration = float(result.stdout.strip())
        speed_factor = original_duration / target_duration

        subprocess.run([
            'ffmpeg', '-i', f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav",
            '-filter:a', f'rubberband=tempo={speed_factor}',
            '-y', f"dubbing_project/dubbed_segments/dub_{i+1}.wav"
        ])

        if os.path.exists(f"dubbing_project/dubbed_segments/temp_{i+1}.mp3"):
            os.remove(f"dubbing_project/dubbed_segments/temp_{i+1}.mp3")
        if os.path.exists(f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav"):
            os.remove(f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav")

def combine_audio_and_video(keep_original_audio, original_audio_volume, voice_choice):
    """ترکیب صدا و ویدیو با زمان‌بندی دقیق"""
    if not os.path.exists('input_video.mp4'):
        raise Exception("لطفاً نام ویدیوی ورودی را به input_video.mp4 تغییر دهید.")

    subs = pysrt.open('/content/audio_fa.srt')

    if keep_original_audio:
        filter_complex = f"[0:a]volume={original_audio_volume}[original_audio];"
    else:
        filter_complex = "[0:a]volume=0[original_audio];"

    valid_segments = []
    for i, sub in enumerate(subs):
        try:
            start_time_ms = (sub.start.hours * 3600 + sub.start.minutes * 60 + sub.start.seconds) * 1000 + sub.start.milliseconds
            filter_complex += f"[{i+1}:a]adelay={start_time_ms}|{start_time_ms}[a{i+1}];"
            valid_segments.append(i)
        except Exception as e:
            print(f"رد کردن سگمنت {i+1} به دلیل مشکل در زمان‌بندی")
            continue

    merge_command = "[original_audio]"
    for i in valid_segments:
        merge_command += f"[a{i+1}]"
    merge_command += f"amix=inputs={len(valid_segments) + 1}:normalize=0[aout]"
    filter_complex += merge_command

    input_files = " ".join([f"-i dubbing_project/dubbed_segments/dub_{i+1}.wav" for i in valid_segments])

    voice_code = voice_choice.split("(")[1].split(")")[0] if "(" in voice_choice else "FA"
    output_filename = f'final_dubbed_video_{voice_code}.mp4'

    command = f'ffmpeg -y -i input_video.mp4 {input_files} -filter_complex "{filter_complex}" -map 0:v -map "[aout]" -c:v copy {output_filename}'
    subprocess.run(command, shell=True)

    if os.path.exists(output_filename):
        if keep_original_audio:
            print(f"ویدیوی نهایی با صدای {voice_choice} و حفظ صدای اصلی با میزان {original_audio_volume*100}% با موفقیت ساخته شد!")
        else:
            print(f"ویدیوی نهایی با صدای {voice_choice} (بدون صدای اصلی) با موفقیت ساخته شد!")
        return output_filename
    else:
        raise Exception("خطا در ساخت ویدیو.")

# ---------------------- رابط کاربری Gradio ----------------------

def main_process(youtube_link, api_key, source_lang, target_lang, voice_choice, keep_original_audio, original_audio_volume):
    try:
        # مرحله 1: پاکسازی فایل‌های قبلی
        clear_previous_files()

        # مرحله 2: دانلود ویدیو و استخراج صدا
        if youtube_link.strip():
            process_youtube(youtube_link)
        else:
            raise Exception("لطفاً لینک یوتیوب را وارد کنید.")

        # مرحله 3: استخراج متن از فایل صوتی
        extract_text_from_audio()

        # مرحله 4: ترجمه زیرنویس
        translate_subtitles(api_key, source_lang, target_lang)

        # مرحله 5: تولید سگمنت‌های صوتی
        asyncio.run(generate_speech(voice_choice))

        # مرحله 6: ترکیب صدا و ویدیو
        output_filename = combine_audio_and_video(keep_original_audio, original_audio_volume, voice_choice)

        return output_filename
    except Exception as e:
        return str(e)

# ایجاد رابط کاربری Gradio
with gr.Blocks() as demo:
    gr.Markdown("# دوبله ویدیو با Gradio")
    
    with gr.Row():
        youtube_link = gr.Textbox(label="لینک ویدیوی یوتیوب")
        api_key = gr.Textbox(label="API Key (Google Generative AI)")
    
    with gr.Row():
        source_lang = gr.Dropdown(["English (EN)", "Persian (FA)", "German (DE)", "French (FR)", "Italian (IT)", "Spanish (ES)", "Chinese (ZH)", "Korean (KO)", "Russian (RU)", "Arabic (AR)", "Japanese (JA)"], label="زبان مبدا", value="English (EN)")
        target_lang = gr.Dropdown(["Persian (FA)", "English (EN)", "German (DE)", "French (FR)", "Italian (IT)", "Spanish (ES)", "Chinese (ZH)", "Korean (KO)", "Russian (RU)", "Arabic (AR)", "Japanese (JA)"], label="زبان مقصد", value="Persian (FA)")
    
    with gr.Row():
        voice_choice = gr.Dropdown(["فرید (FA)", "دلارا (FA)", "Jenny (EN)", "Guy (EN)", "Katja (DE)", "Conrad (DE)", "Denise (FR)", "Henri (FR)", "Isabella (IT)", "Diego (IT)", "Elvira (ES)", "Alvaro (ES)", "Xiaoxiao (ZH)", "Yunyang (ZH)", "SunHi (KO)", "InJoon (KO)", "Svetlana (RU)", "Dmitry (RU)", "Amina (AR)", "Hamed (AR)", "Nanami (JA)", "Keita (JA)"], label="انتخاب گوینده", value="فرید (FA)")
        keep_original_audio = gr.Checkbox(label="حفظ صدای اصلی ویدیو", value=False)
        original_audio_volume = gr.Slider(minimum=0, maximum=1, step=0.005, label="میزان صدای اصلی", value=0.05)
    
    submit_button = gr.Button("شروع دوبله")
    output_video = gr.File(label="ویدیوی نهایی")

    submit_button.click(
        fn=main_process,
        inputs=[youtube_link, api_key, source_lang, target_lang, voice_choice, keep_original_audio, original_audio_volume],
        outputs=output_video
    )

demo.launch(share=True)
