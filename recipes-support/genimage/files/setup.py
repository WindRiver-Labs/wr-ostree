import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="genimage", # Replace with your own username
    version="1.0",
    author="Hongxu Jia",
    author_email="hongxu.jia@windriver.com",
    description="Implementation of Full Image generator with Application SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="todo",
    packages=setuptools.find_packages(),
    entry_points = {
        'console_scripts': [
            'genimage=genimage:main',
            'genyaml=genimage:main_genyaml',
            'exampleyamls=exampleyamls:main_exampleyamls'
        ],
    },
    license="GNU General Public License v2.0",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)

