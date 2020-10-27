import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="appsdk",
    version="1.0",
    author="Qi Chen",
    author_email="qi.chen@windriver.com",
    description="Wind River Linux Assembly Tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="todo",
    packages=setuptools.find_packages(),
    entry_points = {
        'console_scripts': ['appsdk=appsdk:main'],
    },
    license="GNU General Public License v2.0",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)

