import time
from pathlib import Path

from app.local.ollama_client import analyze_image


BASE_DIR = Path(__file__).resolve().parent.parent
FRAME_DIR = BASE_DIR / "data" / "frames"

images = [
    FRAME_DIR / "frame_0000.00.jpg",
    FRAME_DIR / "frame_0002.00.jpg",
    FRAME_DIR / "frame_0000.00.jpg",
    FRAME_DIR / "frame_0002.00.jpg",
]


def main() -> None:
    print(f"총 {len(images)}회 테스트")

    for i, image_path in enumerate(images, start=1):
        print()
        print("=" * 60)
        print(f"[{i}/{len(images)}] {image_path.name}")
        print("=" * 60)

        try:
            result = analyze_image(
                image_path,
                max_retries=1,
            )
            print(result)

        except Exception as error:
            print()
            print("[분석 실패]")
            print(error)

        print("\n5초 대기...")
        time.sleep(5)


if __name__ == "__main__":
    main()