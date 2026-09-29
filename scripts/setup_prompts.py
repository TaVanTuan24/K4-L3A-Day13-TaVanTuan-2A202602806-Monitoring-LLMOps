"""Tạo prompt day13-chat v1/v2 trên Langfuse (safe, idempotent).

Chỉ tạo khi prompt/version chưa tồn tại; không in secret. Việc promote/rollback
label ``production`` chỉ cần một click trên Langfuse UI (xem docs/PROMPT_VERSIONING.md).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from app.cli import configure_utf8_stdio  # noqa: E402

PROMPT_NAME = "day13-chat"
VERSION_1 = "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}"
VERSION_2 = (
    "You are a concise monitoring assistant.\n\n"
    "Feature={{feature}}\n\n"
    "Use the following context:\n{{docs}}\n\n"
    "Question:\n{{message}}\n\n"
    "Answer clearly and concisely."
)


def _version_exists(client, name: str, version: int) -> bool:
    try:
        client.get_prompt(name, version=version, cache_ttl_seconds=0, max_retries=0)
        return True
    except Exception:
        return False


def main() -> int:
    configure_utf8_stdio()
    load_dotenv(REPO_ROOT / ".env")

    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        print("Langfuse chưa cấu hình public/secret key. Bỏ qua (app vẫn chạy local fallback).")
        return 0

    try:
        from langfuse import get_client
        client = get_client()
    except Exception as exc:
        print(f"Không khởi tạo được Langfuse client: {type(exc).__name__}: {exc}")
        return 1

    name = os.getenv("LANGFUSE_PROMPT_NAME", PROMPT_NAME)

    if not _version_exists(client, name, 1):
        try:
            v1 = client.create_prompt(
                name=name,
                prompt=VERSION_1,
                labels=["baseline", "production"],
                type="text",
            )
            print(f"Đã tạo prompt v1 (version={getattr(v1, 'version', '?')}) labels=baseline, production")
        except Exception as exc:
            print(f"Tạo v1 thất bại: {type(exc).__name__}: {exc}")
            return 1
    else:
        print("Prompt v1 đã tồn tại; không tạo lại.")

    if not _version_exists(client, name, 2):
        try:
            v2 = client.create_prompt(
                name=name,
                prompt=VERSION_2,
                labels=["candidate"],
                type="text",
            )
            print(f"Đã tạo prompt v2 (version={getattr(v2, 'version', '?')}) label=candidate")
        except Exception as exc:
            print(f"Tạo v2 thất bại: {type(exc).__name__}: {exc}")
            return 1
    else:
        print("Prompt v2 đã tồn tại; không tạo lại.")

    print("Hoàn tất. Bước UI còn lại: promote/rollback label `production` (Langfuse → Prompts).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())