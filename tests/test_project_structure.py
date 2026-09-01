from pathlib import Path
import unittest


REQUIRED_PATHS = [
    "careertracker/app/main.py",
    "careertracker/app/models",
    "careertracker/app/schemas",
    "careertracker/app/routes",
    "careertracker/app/services",
    "careertracker/app/repositories",
    "careertracker/app/database",
    "careertracker/app/core",
    "tests",
    "migrations",
    "Dockerfile",
    "docker-compose.yml",
    "pyproject.toml",
    "README.md",
    ".env.example",
]


class TestProjectStructure(unittest.TestCase):
    def test_required_structure_exists(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        missing = [path for path in REQUIRED_PATHS if not (repo_root / path).exists()]
        self.assertEqual([], missing, f"Missing required paths: {missing}")


if __name__ == "__main__":
    unittest.main()
