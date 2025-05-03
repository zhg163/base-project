from setuptools import setup, find_packages

setup(
    name="ai_project",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        line.strip() for line in open("requirements.txt") 
        if not line.startswith("#")
    ],
    python_requires=">=3.11.6",
) 