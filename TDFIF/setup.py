from setuptools import setup, find_packages

setup(
    name="tdfif",
    version="0.1.0",
    description="Tour De Force: Interdiction Force - a menu-driven squad RPG "
                 "in the Tour De Force universe.",
    packages=find_packages(include=["tdfif", "tdfif.*"]),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "tdfif=tdfif.app:run",
        ],
    },
)
