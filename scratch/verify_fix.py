import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Setup dummy app config if needed
import os
os.environ["JAVSTORY_MEDIA_ROOT"] = str(PROJECT_ROOT / "data" / "media_test")

from javstory.library.stills.extract import extract_snapshots_auto

def test_snapshots():
    # Find a small video file to test with, or just mock it if we can't find one.
    # For now, we'll just test the logic with a mock if possible, 
    # but since it uses cv2.VideoCapture, we need a real file.
    
    # Check if there is any mp4 file in the workspace
    videos = list(PROJECT_ROOT.glob("**/*.mp4"))
    if not videos:
        print("No video found for testing. Please provide a path to a small mp4 file.")
        return

    test_video = videos[0]
    out_dir = PROJECT_ROOT / "data" / "media_test" / "TEST-001" / "Snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Testing with video: {test_video}")
    print(f"Output directory: {out_dir}")
    
    res = extract_snapshots_auto(test_video, out_dir, target_count=5)
    
    print(f"Extracted {len(res)} snapshots:")
    for p in res:
        print(f"  - {p.name}")
    
    if len(res) == 5:
        print("SUCCESS: All snapshots extracted correctly.")
    else:
        print(f"FAILURE: Expected 5 snapshots, got {len(res)}.")

if __name__ == "__main__":
    test_snapshots()
