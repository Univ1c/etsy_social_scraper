from setuptools import setup, find_packages

setup(
    name='etsy-social-scraper',
    version='1.0.0',
    description='Etsy Social Scraper & Instagram Engagement System',
    author='Univic',
    author_email='ilabeshidavid@example.com',
    packages=find_packages(),
    include_package_data=True,  # Ensure non-code files are included
    package_data={
        '': ['version.txt'],  # Include version.txt in the package
    },
    install_requires=[
        'requests>=2.25.1',
        'beautifulsoup4>=4.9.3',
        'fake-useragent>=0.1.11',
        # Add other dependencies here
    ],
    entry_points={
        'console_scripts': [
            'etsy-scraper=etsy_scraper.main:main',
        ],
    },
    python_requires='>=3.7',
)
