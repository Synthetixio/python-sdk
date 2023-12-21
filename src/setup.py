from setuptools import setup, find_packages

setup(
    name="synthetix",
    version="0.1.2",
    description="Synthetix protocol SDK",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Synthetix DAO",
    packages=find_packages(),
    install_requires=[
        "numpy",
        "pandas",
        "requests",
        "requests_toolbelt",
        "web3>=6.4.0",
        "gql",
    ],
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
    include_package_data=True,
)
