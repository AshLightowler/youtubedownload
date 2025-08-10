from pytubefix import YouTube, Playlist
from pytubefix.cli import on_progress
import subprocess
import os
import re
import mimetypes

# Prompt the user for the YouTube playlist URL
playlist_url = input("Enter the YouTube playlist URL: ")

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
    """Removes illegal characters from a string so it can be used as a filename."""
    sanitized = re.sub(r'[\\/*?:"<>|]', "", title)
    return sanitized[:max_length].strip()

try:
    # Create a Playlist object
    pl = Playlist(playlist_url)
    print(f"\nProcessing playlist: {pl.title}")

    # Process each video in the playlist
    for video in pl.videos:
        try:
            # Use the video object from the playlist, and set the on_progress_callback
            video.register_on_progress_callback(on_progress)
            print(f"\nDownloading: {video.title}")

            # Sanitize the video title to create a valid filename
            video_title = sanitize_filename(video.title)
            video_id = video.video_id  # Get the unique video ID

            # Filter for the desired resolution video-only stream
            video_stream = video.streams.filter(res=resolution, mime_type="video/mp4", progressive=False).first()

            # Download the highest quality audio-only stream
            audio_stream = video.streams.filter(only_audio=True).order_by('abr').desc().first()

            # Check if the desired resolution video stream is available
            if not video_stream:
                print(f"\nVideo stream with resolution {resolution} is not available for '{video.title}'.")
                # Offer to download the highest available resolution
                video_stream = video.streams.filter(only_video=True, mime_type="video/mp4", progressive=False).order_by('resolution').desc().first()
                if video_stream:
                    available_resolution = video_stream.resolution
                    print(f"Downloading the highest available resolution: {available_resolution}")
                else:
                    print(f"No suitable video streams are available for '{video.title}'.")
                    continue  # Skip to the next video

            # Check if the audio stream is available
            if not audio_stream:
                print(f"\nNo audio stream available for '{video.title}'.")
                continue  # Skip to the next video

            # Get file extensions from mime types
            video_extension = mimetypes.guess_extension(video_stream.mime_type) or '.mp4'
            audio_extension = mimetypes.guess_extension(audio_stream.mime_type) or '.webm'

            video_filename = f"{video_title}_{video_id}_video{video_extension}"
            audio_filename = f"{video_title}_{video_id}_audio{audio_extension}"
            output_filename = f"{video_title}.mp4"

            print(f"\nDownloading video stream ({video_stream.resolution})...")
            video_stream.download(filename=video_filename)

            print("\nDownloading audio stream...")
            audio_stream.download(filename=audio_filename)

            # Determine whether to copy or re-encode audio
            if reencode_audio:
                print("\nRe-encoding audio to AAC for compatibility.")
                audio_codec_option = ['-c:a', 'aac', '-b:a', '192k']  # Re-encode audio
            else:
                print("\nCopying original audio stream without re-encoding.")
                audio_codec_option = ['-c:a', 'copy']  # Copy audio

            # Merge video and audio using ffmpeg
            print(f"\nMerging video and audio into '{output_filename}'...")
            command = [
                'ffmpeg',
                '-y',  # Overwrite output file if it exists
                '-i', video_filename,
                '-i', audio_filename,
                '-c:v', 'copy',  # Copy video stream without re-encoding
            ] + audio_codec_option + [
                output_filename
            ]

            # Run the ffmpeg command and handle potential errors
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
                print(f"\nVideo and audio merged successfully into '{output_filename}'.")
            except subprocess.CalledProcessError as e:
                print(f"\nMerging failed for '{video.title}'. Error: {e.stderr}")
                print("Attempting to re-encode both video and audio as a fallback...")
                
                # Fallback: Re-encode both video and audio
                fallback_command = [
                    'ffmpeg',
                    '-y',
                    '-i', video_filename,
                    '-i', audio_filename,
                    '-c:v', 'libx264',  # Re-encode video
                    '-preset', 'medium',
                ] + audio_codec_option + [
                    output_filename
                ]
                try:
                    subprocess.run(fallback_command, check=True, capture_output=True, text=True)
                    print(f"\nVideo and audio re-encoded and merged successfully into '{output_filename}'.")
                except subprocess.CalledProcessError as e_fallback:
                    print(f"\nAll merging attempts failed for '{video.title}'. Error: {e_fallback.stderr}")
                    continue  # Skip to the next video

            # Clean up temporary files
            os.remove(video_filename)
            os.remove(audio_filename)
            print("\nTemporary files removed.")

        except Exception as e:
            print(f"\nAn error occurred while processing video '{video.title}': {e}")
            continue  # Proceed to the next video in the playlist

except Exception as e:
    print(f"\nAn error occurred while processing the playlist: {e}")