import os
from setuptools import setup, find_packages

f = open(os.path.join(os.path.dirname(__file__), 'README.rst'))
readme = f.read()
f.close()

setup(
    name='helix',
    version='1.0',
    description='helix is a django application to implement helix.',
    long_description=readme,
    author='ClearlyEnergy',
    author_email='info@clearlyenergy.com',
    url='https://github.com/ClearlyEnergy/HELIX/tree/master',
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
    ],
)
