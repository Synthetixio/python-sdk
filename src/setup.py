from setuptools import setup, find_packages
setup(
    name='synthetix',
    version='1.0.1',
    description='Synthetix protocol SDK',
    long_description='A library containing helpful functions for interacting with the Synthetix protocol',
    author='Synthetix DAO',
    packages=['synthetix'],
    install_requires=[
        "numpy",
        "pandas",
        "requests",
        "requests_toolbelt",
        "web3>=6.4.0",
        "gql"
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
    python_requires=">=3.8",
    package_data={"synthetix": ["json/*"]},
    include_package_data=True,
)
