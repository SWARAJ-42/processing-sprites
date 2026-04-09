import sys
import base64
from openai import AzureOpenAI
import os
from dotenv import load_dotenv

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

def generate_prompt_bytes(image_bytes, token, rows, cols, num_frames, bgcolor, gif_name):

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

    return f"{token}, {response.choices[0].message.content.strip("\"")}".strip()