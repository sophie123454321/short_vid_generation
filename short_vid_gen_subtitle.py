import os
from gradio_client import Client
import shutil
from mutagen.mp3 import MP3


vid_id = "vid_01"
vid_text = """When you send your email and realize it has a typo..."""

GRADIO_ENDPOINT = os.environ.get("SUBTITLE_ENDPOINT")


if __name__ == "__main__":
	client = Client(GRADIO_ENDPOINT)	

	result = client.predict(
		text = vid_text,
        speaker="Trump",
        top_p=0.95,
        api_name="/predict"
    )
	json_transcription = result[0]
	json_short = result[1]
	srt_short = result[2]
	audio_bytes = result[3]

	output_json_long_file = vid_id + "_subtitle_long.json"
	output_json_short_file = vid_id + "_subtitle_short.json"
	output_srt_short_file = vid_id + "_srt_short.srt"
	output_audio_file = vid_id + "_voice_file.mp3"

	shutil.copy(audio_bytes, output_audio_file)
	shutil.copy(json_short, output_json_short_file)
	shutil.copy(json_transcription, output_json_long_file)
	shutil.copy(srt_short, output_srt_short_file)

	audio = MP3(output_audio_file)
	duration_seconds = audio.info.length

	print(f"Duration of {output_audio_file}: {duration_seconds:.2f} seconds")
