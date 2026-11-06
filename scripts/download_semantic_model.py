"""Explicitly download and initialize the optional local semantic model."""

import os
import sys

os.environ.setdefault("PYTHON_DOTENV_DISABLED", "1")

from app.services.semantic_skill_candidate_service import (  # noqa: E402
    SEMANTIC_MODEL_NAME,
    SemanticModelUnavailable,
    prepare_semantic_model,
)


def main() -> int:
    try:
        prepare_semantic_model()
    except SemanticModelUnavailable:
        print(
            'Semantic model setup failed. Install the optional extra with '
            '`pip install -e ".[semantic]"` and retry.',
            file=sys.stderr,
        )
        return 1
    print(f"Semantic model is ready in the local FastEmbed cache: {SEMANTIC_MODEL_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
