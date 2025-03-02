import yt_dlp
import os
import subprocess
import pysrt
import edge_tts
import asyncio
import shutil

def download_youtube_video(url):
    """دانلود ویدیو و استخراج صدا از یوتیوب"""
    if not url:
        return "لینک یوتیوب وارد نشده!", None, None
    
    # دانلود ویدیو
    video_opts = {'format': 'best', 'outtmpl': 'input_video.mp4'}
    with yt_dlp.YoutubeDL(video_opts) as ydl:
        ydl.download([url])

    # استخراج صدا
    audio_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
        'outtmpl': 'audio'
    }
    with yt_dlp.YoutubeDL(audio_opts) as ydl:
        ydl.download([url])

    return "دانلود و استخراج صدا انجام شد!", "input_video.mp4", "audio.wav"

def transcribe_audio():
    """استخراج متن از فایل صوتی"""
    if not os.path.exists('audio.wav'):
        return "فایل صوتی پیدا نشد!"
    
    os.system('whisper "audio.wav" --model large --output_dir ./ --output_format srt')
    return "متن استخراج شد!", "audio.srt"

async def generate_speech(voice_choice="fa-IR-FaridNeural"):
    """تبدیل متن به گفتار با زمان‌بندی دقیق"""
    os.makedirs('dubbing_project/dubbed_segments', exist_ok=True)
    subs = pysrt.open('audio.srt')

    for i, sub in enumerate(subs):
        start_time = sub.start.seconds + sub.start.milliseconds/1000
        end_time = sub.end.seconds + sub.end.milliseconds/1000
        target_duration = end_time - start_time

        communicate = edge_tts.Communicate(sub.text, voice_choice)
        await communicate.save(f"dubbing_project/dubbed_segments/temp_{i+1}.mp3")

        subprocess.run([
            'ffmpeg', '-i', f"dubbing_project/dubbed_segments/temp_{i+1}.mp3",
            '-y', f"dubbing_project/dubbed_segments/dub_{i+1}.wav"
        ])

    return "صداها تولید شدند!"

def merge_audio_video():
    """ترکیب صدای دوبله با ویدیو"""
    if not os.path.exists('input_video.mp4'):
        return "ویدیو پیدا نشد!"

    subs = pysrt.open('audio.srt')
    filter_complex = "[0:a]volume=0[original_audio];"
    valid_segments = []

    for i, sub in enumerate(subs):
        start_time_ms = (sub.start.hours * 3600 + sub.start.minutes * 60 + sub.start.seconds) * 1000 + sub.start.milliseconds
        filter_complex += f"[{i+1}:a]adelay={start_time_ms}|{start_time_ms}[a{i+1}];"
        valid_segments.append(i)

    merge_command = "[original_audio]" + "".join(f"[a{i+1}]" for i in valid_segments)
    merge_command += f"amix=inputs={len(valid_segments) + 1}:normalize=0[aout]"
    filter_complex += merge_command

    input_files = " ".join([f"-i dubbing_project/dubbed_segments/dub_{i+1}.wav" for i in valid_segments])
    output_filename = "final_dubbed_video.mp4"
    command = f'ffmpeg -y -i input_video.mp4 {input_files} -filter_complex "{filter_complex}" -map 0:v -map "[aout]" -c:v copy {output_filename}'
    subprocess.run(command, shell=True)

    return output_filename
