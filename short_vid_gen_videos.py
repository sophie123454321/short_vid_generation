from short_vid_video_meta_prompt import video_meta_prompt
from threading import Lock
import json
import base64
import os
from openai import AzureOpenAI
from pathlib import Path
from gradio_client import Client, handle_file
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import math
from short_vid_gen_subtitle import vid_id



input_folder = vid_id + "_images"
input_scene_file = vid_id + "_scenes.json"

video_prompt_file = vid_id + "_video_prompts.json" 

output_folder = vid_id + "_videos"
os.makedirs(output_folder, exist_ok=True) 



# Set up endpoints
my_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT")
subscription_key = os.environ.get("AZURE_OPENAI_KEY")


GRADIO_ENDPOINTS = os.environ.get("VIDEO_GEN_ENDPOINTS")
if not GRADIO_ENDPOINTS:
    raise ValueError("Set VIDEO_GEN_ENDPOINTS environment variable (comma-separated URLs).")
clients_urls = [url.strip() for url in GRADIO_ENDPOINTS.split(",")]


# Setup clients and locks
client_objs = [Client(url) for url in clients_urls]
client_locks = [Lock() for _ in client_objs]

maxretry=3

with open(input_scene_file, "r", encoding="utf-8") as f:
    scenes = json.load(f)

def find_files_with_string(folder_path, search_string):
    matching_files = []

    for root, _, files in os.walk(folder_path):
        for filename in sorted(files):
            if search_string in filename:
                file_path = os.path.join(root, filename)
                matching_files.append(file_path)

    return matching_files

def extract_leading_number(file_path):
    filename = Path(file_path).stem 
    parts = filename.split('_')
    if parts and parts[0].isdigit():
        return parts[0]
    return None

search = "PASS"
result_files = find_files_with_string(input_folder, search)

# Now, build the hash table for all scenes
scenehash = dict()
for scene in scenes:
    scene_id = scene.get("scene_id", None)
    scenehash[scene_id] = scene  # Store the entire scene object

def get_GPT4O_client(endpoint, key):
    api_version = "2024-12-01-preview"

    client = AzureOpenAI(
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=key,
    )

    return client

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
    return f"data:image/png;base64,{encoded_string}"


def generate_video_prompt(image_path, scene_title, core_movements):
    prompt_filled = video_meta_prompt.replace("{{ VID SCENE TITLE }}", scene_title)
    prompt_filled = prompt_filled.replace("{{ VID CORE MOVEMENTS }}", core_movements)

    image_url = encode_image_to_base64(image_path)

    client = get_GPT4O_client(my_endpoint, subscription_key)
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful chatbot assistant that creates video prompts for short-form content."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_filled},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]
    )

    return response.choices[0].message.content




def generate_video(video_prompt_dict, index, image_path, vid_len):

    # Assign a client based on index to balance load
    client_idx = int(index) % len(client_objs)
    client = client_objs[client_idx]
    client_lock = client_locks[client_idx]

    with client_lock:
        result = client.predict(
            image=handle_file(image_path),
            base64_image_str="",
            prompt=video_prompt_dict.get("video_prompt", ""),
            negative_prompt=video_prompt_dict.get("negative_prompt", ""),
            video_length=int(vid_len),
            api_name="/predict"
        )
    print(f"[DEBUG] Got result for index {index}: {result}")


    video_path = result["video"]
    if video_path and os.path.exists(video_path):
        dest_path = os.path.join(output_folder, f"scene_{index}_output.mp4")
        shutil.copy(video_path, dest_path)
        print("Video saved to", dest_path)
    else:
        print("Video file not found:", video_path)


def submit_with_retry(prompt_dict, idx, img_path, vlen):
    for attempt in range(maxretry):
        try:
            generate_video(prompt_dict, idx, img_path, vlen)
            return
        except Exception as e:
            print(f"[ERROR] Failed attempt {attempt+1} for index {idx}: {e}")
    print(f"[FAILURE] All retries failed for {idx}")



def store_video_prompts():
    # Step 1: Detect existing videos
    existing_vids = set()
    for f in os.listdir(output_folder):
        if f.startswith("scene_") and f.endswith("_output.mp4"):
            try:
                index = f.split("_")[1]  # e.g., '01' from 'scene_01_output.mp4'
                existing_vids.add(index.zfill(2))
            except:
                continue

    # Step 2: Define expected set 
    expected_vids = {str(i).zfill(2) for i in range(1, len(scenehash)+1)}


    # Step 3: Find missing video indexes
    missing_vids = expected_vids - existing_vids
    print(f"[INFO] Missing videos for scene indexes: {sorted(missing_vids)}")

    # Step 4: Filter result_files (PASS image list)
    filtered_result_files = [
        path for path in result_files
        if extract_leading_number(path).zfill(2) in missing_vids
    ]

    print(f"[INFO] Generating prompts for {len(filtered_result_files)} missing scenes")

    # Step 5: Generate prompts for only the missing image files
    merged_prompts = []
    for image_path in filtered_result_files:
        trycnt = 0
        while trycnt < maxretry:
            trycnt += 1
            try:
                index = extract_leading_number(image_path)
                index = index.zfill(2)
                scene = scenehash.get(index, None)
                if not scene:
                    print(f"[WARNING] No scene found for index {index}")
                    break

                scene_title = scene.get("scene_title", "")
                core_movements = scene.get("core_movements", "")
                vid_length = scene.get("scene_length", "5")

                print(f"[PROMPT] {index}    {image_path}")

                generated_prompt_json = generate_video_prompt(
                    image_path, scene_title, core_movements
                )
                parsed_prompt = json.loads(generated_prompt_json)

                merged_prompts.append({
                    "prompt": parsed_prompt,
                    "index": index,
                    "image_path": image_path,
                    "vid_length": vid_length,
                    "input_vid_length": math.ceil(int(vid_length))
                })
                break  # Exit retry loop on success
            except Exception as e:
                print(f"[ERROR] Failed to generate prompt for {image_path}: {e}")
                continue

    # Step 6: Write to JSON
    with open(video_prompt_file, "w", encoding="utf-8") as f_out:
        json.dump(merged_prompts, f_out, indent=2, ensure_ascii=False)
        print(f"[INFO] Dumped {len(merged_prompts)} prompts to {video_prompt_file}")

        


if __name__ == "__main__":

    store_video_prompts() # generate and store all video prompts

    with open(video_prompt_file, "r", encoding="utf-8") as f:
        merged_prompts = json.load(f)

    # generate all videos from saved prompts
    with ThreadPoolExecutor(max_workers=len(client_objs)) as executor:  # 4 clients = 4 threads
        future_to_info = {}

        for entry in merged_prompts:
            prompt_dict = entry["prompt"]
            index = entry["index"]
            image_path = entry["image_path"]
            input_vid_length = entry["input_vid_length"]

            future = executor.submit(
                submit_with_retry, prompt_dict, index, image_path, input_vid_length
            )
            future_to_info[future] = index

        # display progress
        for future in tqdm(as_completed(future_to_info), total=len(future_to_info), desc="Generating videos"):
            idx = future_to_info[future]
            try:
                future.result()
            except Exception as e:
                print(f"[FATAL] Unhandled exception in task {idx}: {e}")
    