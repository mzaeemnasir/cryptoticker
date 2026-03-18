from setuptools import setup

setup(
    name="cryptoticker",
    version="1.0.0",
    description="Real-time cryptocurrency futures price tracker with live terminal UI",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Muhammad Zaeem Nasir",
    license="MIT",
    py_modules=["cryptoticker"],
    python_requires=">=3.8",
    install_requires=[
        "websocket-client>=1.6.0",
        "art>=6.0",
        'colorama>=0.4.6; sys_platform == "win32"',
    ],
    entry_points={
        "console_scripts": [
            "cryptoticker=cryptoticker:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Topic :: Office/Business :: Financial",
    ],
)
