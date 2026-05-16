FROM jupyter/scipy-notebook

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt