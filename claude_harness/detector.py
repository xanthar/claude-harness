"""Stack and codebase detector for Claude Harness.

Automatically detects:
- Programming language
- Framework
- Database
- Package manager
- Test framework
- Existing structure
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DetectedStack:
    """Detected project stack information."""

    # Core
    language: Optional[str] = None
    language_version: Optional[str] = None
    framework: Optional[str] = None

    # Database
    database: Optional[str] = None
    orm: Optional[str] = None

    # Package management
    package_manager: Optional[str] = None
    dependency_file: Optional[str] = None

    # Testing
    test_framework: Optional[str] = None
    test_directory: Optional[str] = None

    # Structure
    has_git: bool = False
    has_docker: bool = False
    has_kubernetes: bool = False
    has_ci: bool = False
    ci_provider: Optional[str] = None

    # Paths
    source_directory: Optional[str] = None
    venv_path: Optional[str] = None
    env_file: Optional[str] = None

    # Existing Claude setup
    has_claude_md: bool = False
    has_claude_commands: bool = False

    # Detection confidence
    confidence: float = 0.0
    detection_notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "language": self.language,
            "language_version": self.language_version,
            "framework": self.framework,
            "database": self.database,
            "orm": self.orm,
            "package_manager": self.package_manager,
            "dependency_file": self.dependency_file,
            "test_framework": self.test_framework,
            "test_directory": self.test_directory,
            "has_git": self.has_git,
            "has_docker": self.has_docker,
            "has_kubernetes": self.has_kubernetes,
            "has_ci": self.has_ci,
            "ci_provider": self.ci_provider,
            "source_directory": self.source_directory,
            "venv_path": self.venv_path,
            "env_file": self.env_file,
            "has_claude_md": self.has_claude_md,
            "has_claude_commands": self.has_claude_commands,
            "confidence": self.confidence,
            "detection_notes": self.detection_notes,
        }


class StackDetector:
    """Detects project stack and structure."""

    # File patterns for detection
    PYTHON_INDICATORS = {
        "requirements.txt": ("pip", "requirements.txt"),
        "requirements-dev.txt": ("pip", "requirements-dev.txt"),
        "pyproject.toml": ("poetry/pip", "pyproject.toml"),
        "Pipfile": ("pipenv", "Pipfile"),
        "setup.py": ("setuptools", "setup.py"),
        "setup.cfg": ("setuptools", "setup.cfg"),
    }

    PYTHON_FRAMEWORKS = {
        "flask": "Flask",
        "django": "Django",
        "fastapi": "FastAPI",
        "starlette": "Starlette",
        "tornado": "Tornado",
        "bottle": "Bottle",
        "pyramid": "Pyramid",
        "aiohttp": "aiohttp",
    }

    JS_INDICATORS = {
        "package.json": ("npm/yarn", "package.json"),
        "yarn.lock": ("yarn", "package.json"),
        "pnpm-lock.yaml": ("pnpm", "package.json"),
        "bun.lockb": ("bun", "package.json"),
    }

    JS_FRAMEWORKS = {
        "react": "React",
        "next": "Next.js",
        "vue": "Vue.js",
        "nuxt": "Nuxt.js",
        "angular": "Angular",
        "svelte": "Svelte",
        "express": "Express.js",
        "fastify": "Fastify",
        "nestjs": "NestJS",
    }

    DATABASE_INDICATORS = {
        "sqlalchemy": "PostgreSQL/SQLite",
        "psycopg2": "PostgreSQL",
        "psycopg": "PostgreSQL",
        "asyncpg": "PostgreSQL",
        "pymysql": "MySQL",
        "mysql-connector": "MySQL",
        "pymongo": "MongoDB",
        "motor": "MongoDB",
        "redis": "Redis",
        "sqlite3": "SQLite",
        "prisma": "Prisma",
        "mongoose": "MongoDB",
        "typeorm": "TypeORM",
        "sequelize": "Sequelize",
        "pg": "PostgreSQL",
    }

    TEST_FRAMEWORKS = {
        "pytest": "pytest",
        "unittest": "unittest",
        "nose": "nose",
        "jest": "Jest",
        "mocha": "Mocha",
        "vitest": "Vitest",
        "playwright": "Playwright",
        "cypress": "Cypress",
        "selenium": "Selenium",
    }

    def __init__(self, project_path: str):
        """Initialize detector with project path."""
        self.project_path = Path(project_path).resolve()
        self.detected = DetectedStack()

    def detect(self) -> DetectedStack:
        """Run full detection and return results."""
        self._detect_git()
        self._detect_docker()
        self._detect_kubernetes()
        self._detect_ci()
        self._detect_claude_setup()
        self._detect_language_and_framework()
        self._detect_database()
        self._detect_tests()
        self._detect_paths()
        self._calculate_confidence()

        return self.detected

    def _detect_git(self):
        """Detect Git repository."""
        git_dir = self.project_path / ".git"
        self.detected.has_git = git_dir.exists()
        if self.detected.has_git:
            self.detected.detection_notes.append("Git repository detected")

    def _detect_docker(self):
        """Detect Docker setup."""
        dockerfile = self.project_path / "Dockerfile"
        compose = self.project_path / "docker-compose.yml"
        compose_alt = self.project_path / "docker-compose.yaml"

        self.detected.has_docker = (
            dockerfile.exists() or compose.exists() or compose_alt.exists()
        )

    def _detect_kubernetes(self):
        """Detect Kubernetes setup."""
        k8s_dirs = ["kubernetes", "k8s", "kube", "manifests"]
        for dir_name in k8s_dirs:
            k8s_path = self.project_path / dir_name
            if k8s_path.exists() and k8s_path.is_dir():
                self.detected.has_kubernetes = True
                self.detected.detection_notes.append(
                    f"Kubernetes manifests found in {dir_name}/"
                )
                break

    def _detect_ci(self):
        """Detect CI/CD setup."""
        ci_configs = {
            ".github/workflows": "GitHub Actions",
            ".gitlab-ci.yml": "GitLab CI",
            ".circleci": "CircleCI",
            "Jenkinsfile": "Jenkins",
            "azure-pipelines.yml": "Azure Pipelines",
            ".travis.yml": "Travis CI",
            "bitbucket-pipelines.yml": "Bitbucket Pipelines",
        }

        for path, provider in ci_configs.items():
            ci_path = self.project_path / path
            if ci_path.exists():
                self.detected.has_ci = True
                self.detected.ci_provider = provider
                self.detected.detection_notes.append(f"CI detected: {provider}")
                break

    def _detect_claude_setup(self):
        """Detect existing Claude Code setup."""
        claude_dir = self.project_path / ".claude"

        if claude_dir.exists():
            claude_md = claude_dir / "CLAUDE.md"
            commands_dir = claude_dir / "commands"

            self.detected.has_claude_md = claude_md.exists()
            self.detected.has_claude_commands = (
                commands_dir.exists() and any(commands_dir.iterdir())
            )

            if self.detected.has_claude_md:
                self.detected.detection_notes.append(
                    "Existing CLAUDE.md found - will enhance, not replace"
                )

    def _detect_language_and_framework(self):
        """Detect programming language and framework."""
        # Check Python
        for filename, (pkg_mgr, dep_file) in self.PYTHON_INDICATORS.items():
            filepath = self.project_path / filename
            # Also check common subdirectories
            backend_filepath = self.project_path / "backend" / filename

            for check_path in [filepath, backend_filepath]:
                if check_path.exists():
                    self.detected.language = "python"
                    self.detected.package_manager = pkg_mgr
                    self.detected.dependency_file = str(
                        check_path.relative_to(self.project_path)
                    )
                    self._detect_python_framework(check_path)
                    self._detect_python_version()
                    break
            if self.detected.language:
                break

        # Check JavaScript/TypeScript
        if not self.detected.language:
            for filename, (pkg_mgr, dep_file) in self.JS_INDICATORS.items():
                filepath = self.project_path / filename
                if filepath.exists():
                    self.detected.package_manager = pkg_mgr
                    self.detected.dependency_file = filename
                    self._detect_js_framework(filepath)
                    break

    def _detect_python_framework(self, requirements_path: Path):
        """Detect Python framework from requirements file."""
        try:
            content = requirements_path.read_text().lower()

            for indicator, framework in self.PYTHON_FRAMEWORKS.items():
                if indicator in content:
                    self.detected.framework = framework
                    self.detected.detection_notes.append(
                        f"Framework detected: {framework}"
                    )
                    break

            # Detect ORM
            if "sqlalchemy" in content:
                self.detected.orm = "SQLAlchemy"
            elif "django" in content:
                self.detected.orm = "Django ORM"
            elif "peewee" in content:
                self.detected.orm = "Peewee"
            elif "tortoise" in content:
                self.detected.orm = "Tortoise ORM"

        except Exception:
            pass

    def _detect_python_version(self):
        """Detect Python version from various sources."""
        # Check pyproject.toml
        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            try:
                import toml
                data = toml.load(pyproject)
                python_req = data.get("project", {}).get("requires-python", "")
                if python_req:
                    self.detected.language_version = python_req
                    return
            except Exception:
                pass

        # Check .python-version
        python_version = self.project_path / ".python-version"
        if python_version.exists():
            try:
                self.detected.language_version = python_version.read_text().strip()
                return
            except Exception:
                pass

        # Default to 3.11+
        self.detected.language_version = "3.11+"

    def _detect_js_framework(self, package_json_path: Path):
        """Detect JavaScript framework from package.json."""
        try:
            with open(package_json_path) as f:
                pkg = json.load(f)

            deps = {
                **pkg.get("dependencies", {}),
                **pkg.get("devDependencies", {}),
            }

            # Check for TypeScript
            if "typescript" in deps:
                self.detected.language = "typescript"
            else:
                self.detected.language = "javascript"

            # Detect framework
            for indicator, framework in self.JS_FRAMEWORKS.items():
                if indicator in deps or f"@{indicator}" in str(deps):
                    self.detected.framework = framework
                    self.detected.detection_notes.append(
                        f"Framework detected: {framework}"
                    )
                    break

        except Exception:
            self.detected.language = "javascript"

    def _detect_database(self):
        """Detect database from dependencies and config files."""
        # Check .env files for database URLs
        env_files = [".env", ".env.example", ".env.local", "backend/.env"]

        for env_file in env_files:
            env_path = self.project_path / env_file
            if env_path.exists():
                try:
                    content = env_path.read_text().lower()
                    if "postgresql" in content or "postgres" in content:
                        self.detected.database = "PostgreSQL"
                    elif "mysql" in content:
                        self.detected.database = "MySQL"
                    elif "mongodb" in content:
                        self.detected.database = "MongoDB"
                    elif "sqlite" in content:
                        self.detected.database = "SQLite"
                    elif "redis" in content and not self.detected.database:
                        self.detected.database = "Redis"

                    if self.detected.database:
                        self.detected.env_file = env_file
                        break
                except Exception:
                    pass

        # Fallback: check dependencies
        if not self.detected.database and self.detected.dependency_file:
            dep_path = self.project_path / self.detected.dependency_file
            if dep_path.exists():
                try:
                    content = dep_path.read_text().lower()
                    for indicator, db in self.DATABASE_INDICATORS.items():
                        if indicator in content:
                            self.detected.database = db.split("/")[0]
                            break
                except Exception:
                    pass

    def _detect_tests(self):
        """Detect test framework and directory."""
        # Common test directories
        test_dirs = ["tests", "test", "spec", "__tests__", "backend/tests"]

        for test_dir in test_dirs:
            test_path = self.project_path / test_dir
            if test_path.exists() and test_path.is_dir():
                self.detected.test_directory = test_dir
                break

        # Detect test framework from dependencies
        if self.detected.dependency_file:
            dep_path = self.project_path / self.detected.dependency_file
            if dep_path.exists():
                try:
                    content = dep_path.read_text().lower()
                    for indicator, framework in self.TEST_FRAMEWORKS.items():
                        if indicator in content:
                            self.detected.test_framework = framework
                            break
                except Exception:
                    pass

        # Check for pytest.ini or setup.cfg
        if not self.detected.test_framework:
            if (self.project_path / "pytest.ini").exists():
                self.detected.test_framework = "pytest"
            elif (self.project_path / "jest.config.js").exists():
                self.detected.test_framework = "Jest"

    def _detect_paths(self):
        """Detect important paths."""
        # Source directory
        source_dirs = ["src", "app", "lib", "backend", "backend/app"]
        for src_dir in source_dirs:
            src_path = self.project_path / src_dir
            if src_path.exists() and src_path.is_dir():
                self.detected.source_directory = src_dir
                break

        # Virtual environment
        venv_dirs = ["venv", ".venv", "env", ".env", "backend/venv"]
        for venv_dir in venv_dirs:
            venv_path = self.project_path / venv_dir
            if venv_path.exists() and (venv_path / "bin" / "activate").exists():
                self.detected.venv_path = venv_dir
                break

    def _calculate_confidence(self):
        """Calculate detection confidence score."""
        score = 0.0
        max_score = 10.0

        if self.detected.language:
            score += 2.0
        if self.detected.framework:
            score += 2.0
        if self.detected.database:
            score += 1.5
        if self.detected.test_framework:
            score += 1.0
        if self.detected.has_git:
            score += 0.5
        if self.detected.source_directory:
            score += 1.0
        if self.detected.dependency_file:
            score += 1.0
        if self.detected.env_file:
            score += 1.0

        self.detected.confidence = round(score / max_score, 2)


def detect_stack(project_path: str) -> DetectedStack:
    """Convenience function to detect stack."""
    detector = StackDetector(project_path)
    return detector.detect()
