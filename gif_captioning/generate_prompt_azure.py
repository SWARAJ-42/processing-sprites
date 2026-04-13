import base64
from openai import AzureOpenAI
import os
from dotenv import load_dotenv
import tempfile
from PIL import Image
import io

MAX_SIZE = 1024

load_dotenv()

endpoint = os.getenv("ENDPOINT")
deployment = os.getenv("DEPLOYMENT")
subscription_key = os.getenv("SUBSCRIPTION_KEY")
api_version = os.getenv("API_VERSION")

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=endpoint,
    api_key=subscription_key,
)

MAX_COLORS = 256      # limit if needed


def extract_palette(image_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    pixels = img.getdata()
    seen = set()
    colors = []

    for r, g, b, a in pixels:
        if a == 0:
            continue
        key = (r, g, b)
        if key not in seen:
            seen.add(key)
            colors.append(key)
            if len(colors) >= MAX_COLORS:
                break

    return f"COLOR PALLET USED: {", ".join(f"#{r:02X}{g:02X}{b:02X}" for r, g, b in colors)}"

# -----------------------------
# RESIZE (MAX 1024)
# -----------------------------
def resize_if_needed(image):
    w, h = image.size
    scale = min(MAX_SIZE / w, MAX_SIZE / h, 1)

    if scale < 1:
        image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    return image

# -----------------------------
# GET BG COLOR
# -----------------------------
def get_bgcolor(metadata_path, gif_name):
    import json

    with open(metadata_path, "r") as f:
        data = json.load(f)

    for item in data:
        if gif_name in item["media_path"]:
            return item.get("bgcolor", "#ffffff")  # fallback

    return "#ffffff"

def encode_image_bytes(image_bytes):

    return base64.b64encode(image_bytes).decode("utf-8")

def build_instruction(rows, cols, num_frames, bgcolor, gif_name):
    print(gif_name)
    
    examples = """EXAMPLES:
1.
2D character animation, side view of a brown-haired swordsman wearing a grey vest and red sleeves. The character performs a fast two-step attack, stepping forward into a sharp horizontal slash and then smoothly rotating into a wide spinning strike, with the body turning fluidly as the blade follows through in a continuous arc. on a neutral grey background.

2.
2D character animation, side view of a muscular chibi-style fighter with spiky blond hair, wearing an orange sleeveless top, black pants, and gloves. The character executes a quick punch animation, driving one arm forward in a sharp motion while the body leans slightly into the strike, then pulling the arm back into a guarded stance with a controlled and snappy recovery. on a neutral dark background.
"""

    return f"""Generate a single-line descriptive caption for a 2D sprite sheet animation.

STRICT REQUIREMENTS:
- Start with: "2D character animation, side view,"
- Describe the animation motion step-by-step clearly as an animation expert who understands anatomy of characters (be super detailed).
- Keep it as one clean paragraph
- Don't mention anything about frames, you have to write a prompt such that you are a human who is actually watching an animation

SPRITE SHEET CONTEXT:
- The sheet contains {num_frames} frames arranged in {rows} rows and {cols} columns
- Understand the motion by observing the full frame sequence

OUTPUT FORMAT:
- Must start with "2D character animation, side view,"
- Must end with: "on a solid {bgcolor} background."
- Clearly include both appearance and motion

IMPORTANT:
- The sheet background color is {bgcolor}, include it in the ending
- Base the motion strictly on frame progression, not assumptions

HINT (from filename): {gif_name}
"""

def generate_prompt_bytes(sheet, token, rows, cols, num_frames, gif_name, metadata_path, gif_path):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        temp_path = tmp.name
        sheet.save(temp_path)
    
    with open(temp_path, "rb") as f:
        image_bytes = f.read()

    color_pallete = extract_palette(image_bytes)

    sheet = resize_if_needed(sheet)

    bgcolor = get_bgcolor(metadata_path, gif_path.name)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        temp_path = tmp.name
        sheet.save(temp_path)

    with open(temp_path, "rb") as f:
        image_bytes = f.read()

    os.remove(temp_path)

    base64_image = encode_image_bytes(image_bytes)

    instruction = build_instruction(rows, cols, num_frames, bgcolor, gif_name)

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {
                "role": "system",
                "content": "You are a sprite animation prompt generator."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instruction},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        max_completion_tokens=150,
        temperature=1
    )

    # print(response)

    return f"{token}, {response.choices[0].message.content.strip("\"")}\n\n{color_pallete}".strip()