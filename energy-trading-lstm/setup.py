from setuptools import setup, find_packages

setup(
    name='energy-trading-lstm',
    version='0.1.0',
    author='Your Name',
    author_email='your.email@example.com',
    description='A project that integrates an LSTM model for optimizing energy trading decisions.',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'Flask',
        'numpy',
        'pandas',
        'torch',
        'scikit-learn',
        'matplotlib',
        'requests',
        'PyYAML'
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)