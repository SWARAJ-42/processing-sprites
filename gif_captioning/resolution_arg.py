import json
import os

def extract_resolutions(folder_path):
    metadata_path = os.path.join(folder_path, "metadata.json")
    
    if not os.path.exists(metadata_path):
        print("metadata.json not found")
        return

    with open(metadata_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    resolutions = set()

    for item in data:
        width = item.get("width")
        height = item.get("height")
        frames = item.get("num_frames")

        if width and height and frames:
            res_str = f"{width}x{height}x{frames}"
            resolutions.add(res_str)

    # sort for consistency
    resolutions = sorted(resolutions)

    # convert to "x","y","z" format
    output_line = ",".join([f'"{r}"' for r in resolutions])

    output_path = os.path.join(folder_path, "resolution_arg.txt")
    
    with open(output_path, "w") as f:
        f.write(output_line)

    print(f"Saved {len(resolutions)} unique resolutions to {output_path}")


# usage
folder_path = r"C:\Users\marsl\Desktop\Stuff\startup_projects\SpriteLoop\general\processing-sprites\dataset_candidate"
extract_resolutions(folder_path)