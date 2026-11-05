import time
from pathlib import Path

from app.local.ollama_client import analyze_image


BASE_DIR = Path(__file__).resolve().parent.parent
FRAME_DIR = BASE_DIR / "data" / "frames"

IMAGES = [
    FRAME_DIR / "frame_0000.00.jpg",
    FRAME_DIR / "frame_0002.00.jpg",
    FRAME_DIR / "frame_0000.00.jpg",
    FRAME_DIR / "frame_0002.00.jpg",
]


def main() -> None:
    print(f"총 {len(IMAGES)}회 테스트")
    for index, image_path in enumerate(IMAGES, start=1):
        print(f"\n{'=' * 60}\n[{index}/{len(IMAGES)}] {image_path.name}\n{'=' * 60}")
        try:
            print(analyze_image(image_path, max_retries=1))
        except Exception as error:
            print(f"\n[분석 실패]\n{error}")
        print("\n5초 대기...")
        time.sleep(5)


if __name__ == "__main__":
    main()
