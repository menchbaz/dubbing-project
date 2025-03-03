import gradio as gr
import base64
import os
import shutil
import yt_dlp
import pysrt
import edge_tts
import subprocess
import asyncio

# تابع برای آپلود ویدیو و استخراج صدا
def upload_video_and_extract_audio(upload_method, yt_link, file):
    if os.path.exists('input_video.mp4'):
        os.remove('input_video.mp4')

    if os.path.exists('audio.wav'):
        os.remove('audio.wav')

    if os.path.exists('audio.srt'):
        os.remove('audio.srt')

    if os.path.exists('dubbing_project'):
        shutil.rmtree('dubbing_project')

    if upload_method == "YouTube":
        if yt_link.strip():
            video_opts = {'format': 'best', 'outtmpl': 'input_video.mp4'}
            with yt_dlp.YoutubeDL(video_opts) as ydl:
                ydl.download([yt_link])
            audio_opts = {'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}], 'outtmpl': 'audio'}
            with yt_dlp.YoutubeDL(audio_opts) as ydl:
                ydl.download([yt_link])
    else:
        file.save('input_video.mp4')
        os.system('ffmpeg -i input_video.mp4 -vn audio.wav')

    return "Video and audio extracted successfully."

# تابع برای استخراج متن از فایل صوتی
def extract_text_from_audio(extraction_method, file=None):
    if extraction_method == "Whisper":
        if os.path.exists('audio.wav'):
            os.system('whisper "audio.wav" --model large --output_dir ./ --output_format srt')
            os.rename("audio.srt", "audio.srt")
        else:
            return "Please upload an audio file first."
    else:
        file.save('audio.srt')

    return "Subtitle extracted successfully."

# تابع برای ترجمه زیرنویس
def translate_subtitle(method, source_language, target_language, api_key, file=None):
    if method == "Manual Upload":
        file.save('audio.srt')
        return "Subtitle uploaded successfully."
    else:
        genai.configure(api_key=api_key)
        subs = pysrt.open('/content/audio.srt')
        output_filename = '/content/audio_translated.srt'

        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
        def translate_subtitle_with_retry(text):
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Translate the following text to {target_language}:\n\n{text}"
            response = model.generate_content(prompt)
            return response.text

        for sub in subs:
            sub.text = translate_subtitle_with_retry(sub.text)
        
        subs.save(output_filename, encoding='utf-8')
        os.rename(output_filename, 'audio_fa.srt')
        return "Subtitle translated successfully."

# تابع برای تولید سگمنت‌های صوتی
async def generate_speech_segments(voice_choice):
    os.makedirs('dubbing_project/dubbed_segments', exist_ok=True)
    subs = pysrt.open('/content/audio_fa.srt')
    selected_voice = VOICE_MAP.get(voice_choice)
    if not selected_voice:
        return "Invalid voice choice."

    for i, sub in enumerate(subs):
        start_time = sub.start.seconds + sub.start.milliseconds/1000
        end_time = sub.end.seconds + sub.end.milliseconds/1000
        target_duration = end_time - start_time
        communicate = edge_tts.Communicate(sub.text, selected_voice)
        await communicate.save(f"dubbing_project/dubbed_segments/temp_{i+1}.mp3")
        subprocess.run(['ffmpeg', '-i', f"dubbing_project/dubbed_segments/temp_{i+1}.mp3", '-y', f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav"])
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav"], capture_output=True, text=True)
        original_duration = float(result.stdout.strip())
        speed_factor = original_duration / target_duration
        subprocess.run(['ffmpeg', '-i', f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav", '-filter:a', f'rubberband=tempo={speed_factor}', '-y', f"dubbing_project/dubbed_segments/dub_{i+1}.wav"])
        os.remove(f"dubbing_project/dubbed_segments/temp_{i+1}.mp3")
        os.remove(f"dubbing_project/dubbed_segments/temp_wav_{i+1}.wav")

    return "Audio segments generated successfully."

# تابع برای ترکیب صدا و ویدیو
def combine_audio_video(keep_original_audio, original_audio_volume):
    if not os.path.exists('input_video.mp4'):
        return "Please upload the input video as 'input_video.mp4'."

    subs = pysrt.open('/content/audio_fa.srt')
    filter_complex = "[0:a]volume=0[original_audio];" if not keep_original_audio else f"[0:a]volume={original_audio_volume}[original_audio];"
    valid_segments = []

    for i, sub in enumerate(subs):
        try:
            start_time_ms = (sub.start.hours * 3600 + sub.start.minutes * 60 + sub.start.seconds) * 1000 + sub.start.milliseconds
            filter_complex += f"[{i+1}:a]adelay={start_time_ms}|{start_time_ms}[a{i+1}];"
            valid_segments.append(i)
        except Exception as e:
            continue

    merge_command = "[original_audio]" + "".join([f"[a{i+1}]" for i in valid_segments]) + f"amix=inputs={len(valid_segments) + 1}:normalize=0[aout]"
    filter_complex += merge_command
    input_files = " ".join([f"-i dubbing_project/dubbed_segments/dub_{i+1}.wav" for i in valid_segments])
    output_filename = f'final_dubbed_video.mp4'
    command = f'ffmpeg -y -i input_video.mp4 {input_files} -filter_complex "{filter_complex}" -map 0:v -map "[aout]" -c:v copy {output_filename}'
    subprocess.run(command, shell=True)

    return output_filename if os.path.exists(output_filename) else "Error in creating the final video."

# تابع برای پاکسازی فایل‌ها
def clean_files():
    shutil.rmtree('/content', ignore_errors=True)
    return "Previous session files cleaned."

# ایجاد رابط کاربری
voice_choice = gr.Dropdown(["فرید (FA)", "دلارا (FA)", "Jenny (EN)", "Guy (EN)", "Katja (DE)", "Conrad (DE)", "Elvira (ES)", "Alvaro (ES)", "Denise (FR)", "Henri (FR)", "Nanami (JA)", "Keita (JA)", "SunHi (KO)", "InJoon (KO)", "Xiaoxiao (ZH)", "Yunyang (ZH)", "Svetlana (RU)", "Dmitry (RU)", "Amina (AR)", "Hamed (AR)", "Isabella (IT)", "Diego (IT)"], label="Select Voice")

    keep_original_audio = gr.Checkbox(label="Keep Original Audio", value=False)
    original_audio_volume = gr.Slider(label="Original Audio Volume", minimum=0, maximum=1, step=0.005, value=0.05)

    generate_segments_btn = gr.Button("Generate Speech Segments")
    combine_audio_video_btn = gr.Button("Combine Audio and Video")
    clean_files_btn = gr.Button("Clean Previous Session Files")

    output = gr.Textbox(label="Output")

    upload_btn.click(upload_video_and_extract_audio, inputs=[upload_method, yt_link, file], outputs=output)
    extract_btn.click(extract_text_from_audio, inputs=[extraction_method, subtitle_file], outputs=output)
    generate_segments_btn.click(generate_speech_segments, inputs=[voice_choice], outputs=output)
    combine_audio_video_btn.click(combine_audio_video, inputs=[keep_original_audio, original_audio_volume], outputs=output)
    clean_files_btn.click(clean_files, outputs=output)

demo.launch(share=True)
