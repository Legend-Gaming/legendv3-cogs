from setuptools import find_packages, setup

setup(
    name="pychallonge_async",
    description="Module to manage Challonge tournaments within an async context",
    author="Fabien Poupineau (fp12)",
    author_email="fa.nospam@gmail.com",
    packages=find_packages(),
    url="http://github.com/fp12/pychallonge_async",
    version="1.0.0",
    keywords=["tournaments", "challonge"],
    install_requires=["iso8601==0.1.11", "aiohttp"],
)
