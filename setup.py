"""
Setup file for tubes.
"""

from setuptools import setup, find_packages

setup(
    name='Tubes',
    version='0.2.0',
    description="""
    Flow control and backpressure for event-driven applications.
    """,
    license="MIT",
    url="https://github.com/twisted/tubes/",

    packages=find_packages(exclude=[]),
    package_dir={'tubes': 'tubes'},
    install_requires=[
        "characteristic",
        "six",
        "Twisted",
    ],
    include_package_data=True,
)
