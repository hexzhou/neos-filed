"""从 YGOPro 场地图仓库生成 Neos 使用的 WebP 和卡号清单。"""

import argparse
import concurrent.futures
import json
from pathlib import Path
import subprocess
import tempfile

UPSTREAM = "https://code.moenext.com/mycard/ygopro-images-field.git"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public/neos-assets/fields"
QUALITY = 85
METHOD = 6


def synchronize(source: Path, revision: str | None, output: Path):
    files = {}
    for image in sorted(source.iterdir()):
        if (
            not image.is_file()
            or not image.stem.isascii()
            or not image.stem.isdecimal()
            or image.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp")
        ):
            continue
        code = int(image.stem)
        if code <= 0:
            continue
        if code in files:
            raise ValueError(f"卡号 {code} 存在重复图片，无法确定应使用哪个文件")
        files[code] = image
    if not files:
        raise ValueError("来源目录没有场地图，未修改已发布资源")

    encoder_version = subprocess.check_output(["cwebp", "-version"], text=True).strip()
    output.parent.mkdir(parents=True, exist_ok=True)
    # 图片和清单在临时目录一起生成，转换失败时保留上一次可用的资源。
    with tempfile.TemporaryDirectory(prefix=".neos-filed-", dir=output.parent) as temp:
        generated = Path(temp) / "fields"
        generated.mkdir()

        def convert(item):
            code, image = item
            subprocess.run(
                [
                    "cwebp", "-quiet", "-q", str(QUALITY), "-m", str(METHOD),
                    str(image), "-o", str(generated / f"{code}.webp"),
                ],
                check=True,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(convert, files.items()))
        (generated / "manifest.json").write_text(
            json.dumps(sorted(files), indent=2) + "\n", encoding="utf-8",
        )
        (generated / "source.json").write_text(
            json.dumps({
                "source": UPSTREAM if revision else "local field directory",
                "revision": revision,
                "count": len(files),
                "format": "WebP",
                "encoder": "cwebp",
                "encoderVersion": encoder_version,
                "quality": QUALITY,
                "method": METHOD,
            }, indent=2) + "\n",
            encoding="utf-8",
        )
        # 替换整套资源也会移除上游已删除的图片，避免清单和目录逐渐不一致。
        backup = Path(temp) / "previous"
        if output.exists():
            output.rename(backup)
        try:
            generated.rename(output)
        except OSError:
            if backup.exists():
                backup.rename(output)
            raise
    print(f"Synchronized {len(files)} field illustrations as WebP ({revision or 'local'})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, help="可选的本地 field 目录")
    parser.add_argument("--revision", help="上游提交或分支，默认 master")
    args = parser.parse_args()
    if args.source:
        synchronize(args.source, args.revision, OUTPUT)
        return
    with tempfile.TemporaryDirectory(prefix="neos-filed-upstream-") as temp:
        subprocess.run(["git", "init", "-q", temp], check=True)
        subprocess.run([
            "git", "-C", temp, "fetch", "--depth=1", UPSTREAM, args.revision or "master",
        ], check=True)
        subprocess.run(["git", "-C", temp, "checkout", "-q", "--detach", "FETCH_HEAD"], check=True)
        revision = subprocess.check_output(
            ["git", "-C", temp, "rev-parse", "HEAD"], text=True,
        ).strip()
        synchronize(Path(temp) / "field", revision, OUTPUT)


if __name__ == "__main__":
    main()
