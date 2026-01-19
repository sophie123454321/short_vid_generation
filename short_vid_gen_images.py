from gradio_client import Client
from tqdm import tqdm
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import base64
from openai import AzureOpenAI
from short_vid_evaluation import editing_eval_prompt
import threading
from short_vid_gen_subtitle import vid_id




my_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
subscription_key = os.environ.get("AZURE_OPENAI_KEY")
api_version = "2024-12-01-preview"

# Gradio endpoints (comma-separated in env variable)
GRADIO_ENDPOINTS = os.environ.get("IMAGE_GEN_ENDPOINTS")
if not GRADIO_ENDPOINTS:
    raise ValueError("Set IMAGE_GEN_ENDPOINTS environment variable (comma-separated list of URLs).")




endpoints = [url.strip() for url in GRADIO_ENDPOINTS.split(",")]

clients = [Client(url) for url in endpoints]
# Create a lock for each client
client_locks = [threading.Lock() for _ in clients]

input_file= vid_id + "_scenes.json"
output_dir = vid_id + "_images"
os.makedirs(output_dir, exist_ok=True)

# Load the JSON array
with open(input_file, "r", encoding="utf-8") as f_read:
    scenes = json.load(f_read)  # scenes is now a list of scene dicts
# Creating a dictionary of image prompts and global_idx
all_image_prompt = []
for idx, scene in enumerate(scenes):
    prompt = scene.get("image_prompt", "").strip()
    global_idx = scene.get("scene_id", None)
    try:
        global_idx = int(global_idx)
        print("prompt read at global_idx: " + str(global_idx))
    except:
        print("scene_id not found at scene_id " + str(idx+1) + ", defaulting to fallback")
        global_idx = idx + 1
    all_image_prompt.append((prompt, global_idx))


# Define task for each image generation
def generate_image(input_prompt, global_idx):

    max_attempts = 20
    attempt = 0
    client_idx = global_idx % len(clients)
    client = clients[client_idx]
    client_lock = client_locks[client_idx]

    current_prompt = input_prompt


    while attempt < max_attempts:
        attempt+=1
        print(f"sending to client {client_idx}, global_idx [{global_idx}], attempt {attempt}")

        try:
            with client_lock:
                result = client.predict(
                    prompt=current_prompt.strip(),
                    size="landscape",
                    api_name="/predict"
                )

            evaluation_raw = evaluate_instruction_following(result, current_prompt.strip())

            try:
                eval_result = json.loads(evaluation_raw)
            except json.JSONDecodeError:
                print(f"[{global_idx}] Attempt {attempt}: Failed to parse evaluation JSON:\n{evaluation_raw}")
                continue  # skip this iteration of the loop if response isn't valid JSON

            eval_status = eval_result.get("evaluation", "").upper()
            explanation = eval_result.get("explanation", "")
            new_prompt = eval_result.get("new_prompt", "")

            if (eval_status == "PASS"):
                print(f"\n[{global_idx}] image passes")
                with open(result, "rb") as img_file:
                    image_bytes = img_file.read()
                attempt_filename = os.path.join(output_dir, f"{global_idx}_attempt{attempt}_PASS.png")
                attempt = max_attempts
                
            else:
                print(f"\n[{global_idx}] attempt" + str(attempt) + f" image fails. Current prompt: {current_prompt}. \nExplanation: {explanation}. \nNew prompt: {new_prompt}")
                with open(result, "rb") as img_file:
                    image_bytes = img_file.read()
                attempt_filename = os.path.join(output_dir, f"{global_idx}_attempt{attempt}_FAIL.png")
                current_prompt = new_prompt

            with open(attempt_filename, "wb") as f_out:
                    f_out.write(image_bytes)


        except Exception as e:
            print(f"[ERROR] idx [{global_idx}] failed: {e}. Current prompt: {current_prompt}")
    
    return (global_idx, None)  # Return the global index and the result file path

def get_GPT4O_client(endpoint):
    return AzureOpenAI(    
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=subscription_key,
    )

def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
    
def evaluate_instruction_following(input_img_path, instructions):
    
    client = get_GPT4O_client(my_endpoint)
    input_image_b64 = encode_image(input_img_path)

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": "You are a helpful chatbot assistant who is an expert in image evaluation and instruction-following assessment."},
            
            {"role": "user","content": [
                    {"type": "text", "text": editing_eval_prompt},
                    {"type": "text", "text": "data: image_prompt:" + instructions},
                    {"type": "text", "text": "input_image:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{input_image_b64}"}},
                ]
            }
        ]
    )
    
    return response.choices[0].message.content




# targeting generation for missing images

# Find existing PASS images in output_dir
existing_pass_ids = set()
for filename in os.listdir(output_dir):
    if filename.endswith("_PASS.png"):
        try:
            idx = int(filename.split("_")[0])
            existing_pass_ids.add(idx)
        except ValueError:
            continue

# Filter through missing scene_ids
target_range = set(range(1, len(all_image_prompt)+1))
missing_ids = target_range - existing_pass_ids
filtered_image_prompt = [(prompt, idx) for prompt, idx in all_image_prompt if idx in missing_ids]

print(f"Total missing: {len(filtered_image_prompt)} — IDs: {sorted(missing_ids)}")

# Only generate images for missing scene_ids
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = [
        executor.submit(generate_image, prompt, global_idx)
        for prompt, global_idx in filtered_image_prompt
    ]

    for future in tqdm(as_completed(futures), total=len(futures)):
        global_idx, image_bytes = future.result()



"""
# targeted generation at a single scene in a chapter:

# Choose the global_idx to generate
target_global_idx = 20

# Filter input to just that one
filtered_image_prompt = [(prompt, idx) for prompt, idx in all_image_prompt if idx == target_global_idx]

# Run generation only for that index
with ThreadPoolExecutor(max_workers=1) as executor:
    futures = [
        executor.submit(generate_image, prompt, global_idx)
        for prompt, global_idx in filtered_image_prompt
    ]

    for future in tqdm(as_completed(futures), total=len(futures)):
        global_idx, image_bytes = future.result()



# generate all images in a chapter:
    
# Use thread pool to run parallel generation
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = [
        executor.submit(generate_image, prompt, global_idx)
        for prompt, global_idx in all_image_prompt
    ]

    for future in tqdm(as_completed(futures), total=len(futures)):
        global_idx, image_bytes = future.result()
"""     
