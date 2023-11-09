:: Requires twine~=4.0.2 to be installed
:: This script will build your package and attempt to upload it to pypi using the metadata in setup.py

cd ..
python setup.py sdist
twine upload dist/*

pause
