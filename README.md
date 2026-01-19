# Short Video Generation Pipeline

This project is a multi-step pipeline for generating short videos from user-provided text, made for platforms like TikTok, Instagram Reels, and Youtube Shorts. The pipeline handles subtitle creation, image prompt generation, image generation with evaluation, and video clip generation.

Each step leverages LLMs (Azure OpenAI GPT-4.1) and Gradio endpoints for audio, image, and video generation.

---

## Features

-Converts user text into an audio file with subtitles using a Gradio endpoint.

-Generates image prompts guided by optional seed scenes.

-Generates images for each prompt, with evaluation using GPT-4.1 to ensure high-quality results.

-Generates video clips from images, with multiple takes for user selection.

-Fully configurable using environment variables for endpoints and API keys.

-Supports parallel processing for faster image and video generation.

---

## Requirements

Python 3.10+

---

## Packages

pip install openai gradio_client tqdm mutagen

---

## Endpoints needed

* short_vid_gen_subtitle.py	: Gradio endpoint for audio and subtitle generation
* short_vid_gen_image_prompts.py : Azure OpenAI GPT-4.1 endpoint + subscription key
* short_vid_gen_images.py : Azure OpenAI GPT-4.1 endpoint + subscription key, plus one or more image-generation Gradio endpoints
* short_vid_gen_videos.py : Azure OpenAI GPT-4.1 endpoint + subscription key, plus one or more video-generation Gradio endpoints

---

## Environment Variables

Set the following environment variables before running the scripts:

* Azure OpenAI GPT-4.1
export AZURE_OPENAI_ENDPOINT="https://<your-resource>.cognitiveservices.azure.com/"
export AZURE_OPENAI_KEY="<your-azure-key>"

* Gradio endpoints for video or image generation (comma-separated URLs)
export VIDEO_GEN_ENDPOINTS="https://<gradio-url-1>,https://<gradio-url-2>"
export IMAGE_GEN_ENDPOINTS="https://<gradio-url-1>,https://<gradio-url-2>"

---

## Usage

1. Generate Audio and Subtitles
python short_vid_gen_subtitle.py
* Input: A user-created text line.
* Output: Subtitle file and background voice file for your video.

2. Generate Image Prompts
python short_vid_gen_image_prompts.py
* Input: Subtitle text from the previous step.
* Output: JSON file containing image prompts for each scene.
* Optional: Seed scenes to guide the LLM and a desired video length.

3. Generate Images
python short_vid_gen_images.py
* Input: Image prompts from the previous step.
* Output: Images for each scene, saved after evaluation passes.
* Each image is evaluated by a GPT-4.1 LLM to ensure that instructions are followed. The script continues generating images until all images pass evaluation or max_attempts is reached.
* Can be rerun multiple times without overwriting previous PASSED images.

4. Generate Videos
python short_vid_gen_videos.py
* Input: Images from the previous step.
* Output: Video clips for each scene.
* This script generates video prompts using GPT-4.1, then uses those prompts to generate videos. Each video is generated 3 times to allow the user to pick the best one.
* Can be rerun multiple times without overwriting previously generated videos.

---

## File Structure

short_vid_generation/

│

├─ short_vid_gen_subtitle.py

├─ short_vid_gen_image_prompts.py

├─ short_vid_gen_images.py

├─ short_vid_gen_videos.py

├─ short_vid_video_meta_prompt.py

├─ short_vid_evaluation.py

├─ short_vid_gen_subtitle.py

├─ <vid_id>_*.json  # generated subtitles, prompts, scenes

├─ <vid_id>_images/  # generated images

├─ <vid_id>_videos/  # generated video clips

└─ README.md

---

## Notes

-Ensure your environment variables are properly set before running any scripts.

-Image generation includes evaluation by GPT-4.1, but video generation does not perform evaluation. The video model outputs directly from the prompts.

-Retry logic is included for both images and videos to handle transient API errors.

-Scripts must be run in order for best results: subtitles -> image prompts -> images -> videos

---

# Sample result

User input: 
* vid_text = """When you send your email and realize it has a typo..."""
* vid_duration = "15"
* seed_scenes = "1) A small orange cat sits like a human slouched on an office chair. It looks sad. 2) The cat puts its forehead on the table while banging a fist at the table. 3) A view of the keyboard as a fluffy paw presses send."

Final result: https://www.youtube.com/shorts/IC9rqnvBRWU

Note: editing and background audio added manually



