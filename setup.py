"""Claude Harness - AI Workflow Optimization Tool."""
from setuptools import setup, find_packages

setup(
    name="claude-harness",
    version="1.0.0",
    description="Workflow harness for optimizing Claude Code sessions",
    author="Morten Elmstroem Hansen",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "claude_harness": ["templates/*", "templates/hooks/*"],
    },
    install_requires=[
        "click>=8.1.0",
        "jinja2>=3.1.0",
        "rich>=13.0.0",
        "questionary>=2.0.0",
        "pyyaml>=6.0",
        "toml>=0.10.0",
        "playwright>=1.40.0",
    ],
    entry_points={
        "console_scripts": [
            "claude-harness=claude_harness.cli:main",
            "ch=claude_harness.cli:main",  # Short alias
        ],
    },
    python_requires=">=3.10",
)
