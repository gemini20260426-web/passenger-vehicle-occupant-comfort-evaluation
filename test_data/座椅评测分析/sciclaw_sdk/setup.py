from setuptools import setup, find_packages

setup(
    name="sciclaw-sdk",
    version="1.0.0",
    description="SciClaw 乘用车座椅评测离线分析SDK",
    author="SciClaw",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.21",
        "scipy>=1.7",
        "pandas>=1.3",
        "matplotlib>=3.4",
        "python-docx>=0.8",
    ],
    extras_require={
        "charts": ["matplotlib>=3.4"],
        "report": ["python-docx>=0.8"],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
