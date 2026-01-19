from short_vid_meta_prompt import meta_prompt
import json
from openai import AzureOpenAI
from short_vid_gen_subtitle import vid_id, vid_text
import os



vid_duration = "15"
seed_scenes = "1) A small orange cat sits like a human slouched on an office chair. It looks sad. 2) The cat puts its forehead on the table while banging a fist at the table. 3) A view of the keyboard as a fluffy paw presses send."


# Read endpoint and key from environment variables
my_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
subscription_key = os.environ.get("AZURE_OPENAI_KEY")


def get_GPT4O_client(endpoint, key):
    api_version = "2024-12-01-preview"
    client = AzureOpenAI(
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=key,
    )
    return client



def generate_image_prompts():

    prompt_filled = meta_prompt.replace("{{VID_CAPTION}}", vid_text)
    prompt_filled = prompt_filled.replace("{{VID_DURATION}}", vid_duration)
    prompt_filled = prompt_filled.replace("{{SEED_SCENES}}", seed_scenes)

    client = get_GPT4O_client(my_endpoint, subscription_key)
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": "You are a helpful chatbot assistant that creates scenes for short videos."},
            {"role": "user", "content": prompt_filled}
        ]
    )
    
    return response.choices[0].message.content



if __name__ == "__main__":

    output_file = vid_id + "_scenes.json" # output file for generated scenes
    generated_prompts_json = generate_image_prompts()
    scenes = json.loads(generated_prompts_json)   
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(scenes, f, indent=2, ensure_ascii=False)
        print("saved to ", output_file)


    
    
    

    
    
