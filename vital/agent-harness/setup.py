from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-vital",
    version="1.0.0",
    description="CLI harness for the Vital wavetable synthesizer",
    author="cli-anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-vital=cli_anything.vital.vital_cli:main",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Multimedia :: Sound/Audio :: Sound Synthesis",
    ],
)
