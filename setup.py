from setuptools import find_packages, setup

with open("requirements.txt", encoding="utf-8") as f:
    requirements = [
        line.strip()
        for line in f
        if line.strip() and not line.startswith("#") and not line.startswith("-")
    ]

setup(
    name="idle-sense",
    version="2.0.0",
    description="Idle-Sense Distributed Computing Platform",
    author="Idle-Sense Team",
    packages=find_packages(
        include=[
            "src",
            "src.*",
            "config",
            "config.*",
            "legacy",
            "legacy.*",
            "serializer",
            "serializer.*",
            "security_audit",
            "security_audit.*",
        ]
    ),
    python_requires=">=3.9",
    install_requires=requirements,
)
