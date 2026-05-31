from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="essaproxy",
    version="1.0.0",
    author="Jeswin Sunny",
    author_email="jeswinsunny@example.com",
    description="A High-Performance Layer 7 HTTP Reverse Proxy and Load Balancer",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jeswintesting-spec/EssaProxy",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Internet :: Proxy Servers",
    ],
    python_requires=">=3.11",
    install_requires=[
        "redis>=5.0.0",
    ],
    entry_points={
        "console_scripts": [
            "essaproxy=essaproxy.cli:main",
        ],
    },
)
