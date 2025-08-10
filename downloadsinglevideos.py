from pytubefix import YouTube
from pytubefix.cli import on_progress
import subprocess
import os
import re
import mimetypes

# Prompt the user for the YouTube video URLs
urls = input("Enter the YouTube video URLs (separated by commas): ")

# Split the URLs into a list
url_list = [url.strip() for url in urls.split(",")]

# Prompt the user for the desired resolution
resolution = input("Enter the desired video resolution (e.g., 1080p, 720p): ")

# Prompt the user for audio encoding preference
audio_choice = input("Do you want to re-encode audio to AAC for compatibility? (yes/no): ").strip().lower()
if audio_choice in ['yes', 'y']:
    reencode_audio = True
else:
    reencode_audio = False

# Function to sanitize the filename
def sanitize_filename(title, max_length=200):
    sanitized = re.sub(r'[\\/*?:"<>|]', "", title)
    return sanitized[:max_length].strip()

# Process each URL in the list
for url in url_list:
    try:
        # Create a YouTube object
        yt = YouTube(url, on_progress_callback=on_progress)
        print(f"\nDownloading: {yt.title}")

        # Sanitize the video title to create a valid filename
        video_title = sanitize_filename(yt.title)
        video_id = yt.video_id  # Get the unique video ID from the URL

        # Filter for the desired resolution video-only stream
        video_stream = yt.streams.filter(res=resolution, mime_type="video/mp4", progressive=False).first()

        # Download the highest quality audio-only stream
        audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()

        # Check if the desired resolution video stream is available
        if not video_stream:
            print(f"\nVideo stream with resolution {resolution} is not available.")
            # Offer to download the highest available resolution
            video_stream = yt.streams.filter(only_video=True, mime_type="video/mp4", progressive=False).order_by('resolution').desc().first()
            if video_stream:
                available_resolution = video_stream.resolution
                print(f"Downloading the highest available resolution: {available_resolution}")
            else:
                print("No suitable video streams are available.")
                continue  # Skip to the next URL

        # Check if the audio stream is available
        if not audio_stream:
            print("\nNo audio stream available for this video.")
            continue  # Skip to the next URL

        # Get file extensions from mime types
        video_extension = mimetypes.guess_extension(video_stream.mime_type)
        audio_extension = mimetypes.guess_extension(audio_stream.mime_type)

        if not video_extension:
            video_extension = '.mp4'  # Default to .mp4 if unknown
        if not audio_extension:
            audio_extension = '.webm'  # Default to .webm if unknown

        video_filename = f"{video_title}_{video_id}_video{video_extension}"
        audio_filename = f"{video_title}_{video_id}_audio{audio_extension}"
        output_filename = f"{video_title}.mp4"

        print(f"\nDownloading video stream ({video_stream.resolution})...")
        video_path = video_stream.download(filename=video_filename)

        print("\nDownloading audio stream...")
        audio_path = audio_stream.download(filename=audio_filename)

        # Determine whether to copy or re-encode audio
        if reencode_audio:
            print("\nRe-encoding audio to AAC for compatibility.")
            audio_codec_option = ['-c:a', 'aac', '-b:a', '192k']  # Re-encode audio
        else:
            print("\nCopying original audio stream without re-encoding.")
            audio_codec_option = ['-c:a', 'copy']  # Copy audio

        # Merge video and audio
        print(f"\nMerging video and audio into '{output_filename}'...")
        command = [
            'ffmpeg',
            '-y',
            '-i', video_filename,
            '-i', audio_filename,
            '-c:v', 'copy',        # Copy video stream
        ] + audio_codec_option + [
            output_filename
        ]

        # Run the command and handle errors
        try:
            subprocess.run(command, check=True)
            print(f"\nVideo and audio merged successfully into '{output_filename}'.")
        except subprocess.CalledProcessError as e:
            print("\nMerging failed. Attempting to re-encode video and audio...")
            # Re-encode both video and audio
            command = [
                'ffmpeg',
                '-y',
                '-i', video_filename,
                '-i', audio_filename,
                '-c:v', 'libx264',    # Re-encode video
            ] + audio_codec_option + [
                '-preset', 'medium',
                output_filename
            ]
            try:
                subprocess.run(command, check=True)
                print(f"\nVideo and audio re-encoded and merged successfully into '{output_filename}'.")
            except subprocess.CalledProcessError as e:
                print("\nAll merging attempts failed.")
                print(e)
                continue  # Skip to the next URL

        # Clean up temporary files
        os.remove(video_filename)
        os.remove(audio_filename)
        print("\nTemporary files removed.")

    except Exception as e:
        print(f"\nAn error occurred while processing URL '{url}': {e}")
        continue  # Proceed to the next URL
