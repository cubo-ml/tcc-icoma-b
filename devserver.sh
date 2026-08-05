#!/bin/sh
source .venv/bin/activate
python -u -m flask --app main run -p $PORT --debug
pip install --update
pip install numpy pandas
pip install matplotlib seaborn
pip install scipy statsmodels
pip install scikit-learn
pip install dask matplotlib
pip install flask
pip install flask-cors
pip install google-generativeai
npm install update